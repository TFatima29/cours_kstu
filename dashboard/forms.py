from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from accounts.models import User
from accounts.services import LOGIN_RE
from courses.models import Category, Course, Lesson, Level, LibraryItem, Material
from quizzes.models import Choice, Question

MAX_VIDEO_MB = 500
MAX_MATERIAL_MB = 50
MAX_COVER_MB = 5


def _check_size(file, limit_mb):
    if file and hasattr(file, "size") and file.size > limit_mb * 1024 * 1024:
        raise forms.ValidationError(f"Файл больше {limit_mb} МБ.")
    return file


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["title", "category", "difficulty", "price", "short_description", "description", "cover", "is_published"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "cover": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["price"].required = False

    def clean_price(self):
        return self.cleaned_data.get("price") or 0

    def clean_cover(self):
        return _check_size(self.cleaned_data.get("cover"), MAX_COVER_MB)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "order"]


class LevelForm(forms.ModelForm):
    class Meta:
        model = Level
        fields = ["title", "order", "pass_threshold"]


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title", "order", "description", "video_file", "video_url", "library_video", "library_materials"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "video_file": forms.ClearableFileInput(attrs={"accept": "video/mp4,video/webm,video/quicktime"}),
            "library_materials": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["library_video"].queryset = LibraryItem.objects.filter(kind=LibraryItem.Kind.VIDEO)
        self.fields["library_video"].empty_label = "— не выбрано —"
        self.fields["library_materials"].queryset = LibraryItem.objects.filter(kind=LibraryItem.Kind.FILE)

    def clean_video_file(self):
        return _check_size(self.cleaned_data.get("video_file"), MAX_VIDEO_MB)

    def clean(self):
        cleaned = super().clean()
        sources = [bool(cleaned.get("video_file")), bool(cleaned.get("video_url")), bool(cleaned.get("library_video"))]
        if sum(sources) > 1:
            self.add_error("video_url", "Укажите что-то одно: файл видео, ссылку или видео из библиотеки.")
        return cleaned


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ["title", "file"]

    def clean_file(self):
        return _check_size(self.cleaned_data.get("file"), MAX_MATERIAL_MB)


class LibraryItemForm(forms.ModelForm):
    """Материал библиотеки: видео до 500 МБ или файл до 50 МБ."""

    class Meta:
        model = LibraryItem
        fields = ["title", "file", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file and hasattr(file, "size") and hasattr(file, "content_type"):
            is_video = file.name.rsplit(".", 1)[-1].lower() in ("mp4", "webm", "mov", "m4v")
            _check_size(file, MAX_VIDEO_MB if is_video else MAX_MATERIAL_MB)
        return file


MaterialFormSet = inlineformset_factory(Lesson, Material, form=MaterialForm, extra=2, can_delete=True)


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["text", "order"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3})}


class BaseChoiceFormSet(BaseInlineFormSet):
    """Минимум два варианта ответа и ровно один правильный."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        filled = [
            f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("text")
        ]
        if len(filled) < 2:
            raise forms.ValidationError("Добавьте минимум два варианта ответа.")
        correct = sum(1 for f in filled if f.cleaned_data.get("is_correct"))
        if correct != 1:
            raise forms.ValidationError("Отметьте ровно один правильный вариант.")


ChoiceFormSet = inlineformset_factory(
    Question, Choice, fields=["text", "is_correct"], formset=BaseChoiceFormSet, extra=4, max_num=8, can_delete=True
)


def _course_choices():
    return Course.objects.order_by("title")


class CourseAccessField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        price = "бесплатно" if obj.is_free else f"{obj.price:g} сом"
        hidden = "" if obj.is_published else ", скрыт"
        return f"{obj.title} ({price}{hidden})"


class UserFieldsMixin:
    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if not name:
            raise forms.ValidationError("Укажите имя.")
        return name

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Пользователь с таким e-mail уже есть.")
        return email

    def clean_login(self):
        login = (self.cleaned_data.get("login") or "").strip().lower()
        if not login:
            return None
        if not LOGIN_RE.match(login):
            raise forms.ValidationError("От 3 до 50 символов: латинские буквы, цифры, точка, дефис, подчёркивание.")
        qs = User.objects.filter(login__iexact=login)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Такой логин уже занят.")
        return login


class UserCreateForm(UserFieldsMixin, forms.ModelForm):
    """А-5. Администратор добавляет студента: логин и пароль генерируются и отправляются на e-mail."""

    courses = CourseAccessField(
        label="Доступ к курсам",
        queryset=Course.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Отметьте курсы, которые студент купил. Он увидит только их.",
    )

    class Meta:
        model = User
        fields = ["full_name", "email", "login", "is_staff"]
        labels = {"is_staff": "Администратор платформы"}
        help_texts = {"login": "Можно оставить пустым — логин сгенерируется из e-mail."}
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Фамилия и имя"}),
            "email": forms.EmailInput(attrs={"placeholder": "name@example.com"}),
            "login": forms.TextInput(attrs={"placeholder": "например, nurgul.a"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["courses"].queryset = _course_choices()


class UserEditForm(UserFieldsMixin, forms.ModelForm):
    """Изменение данных пользователя администратором, включая логин и пароль."""

    new_password = forms.CharField(
        label="Новый пароль",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
        help_text="Оставьте пустым, чтобы не менять. Минимум 8 символов.",
    )
    generate_password = forms.BooleanField(label="Сгенерировать новый пароль автоматически", required=False)
    send_email = forms.BooleanField(
        label="Отправить логин и пароль на e-mail", required=False, initial=True,
        help_text="Письмо уходит, только если пароль изменён.",
    )

    class Meta:
        model = User
        fields = ["full_name", "email", "login", "is_staff", "is_active"]
        labels = {"is_staff": "Администратор платформы", "is_active": "Активен (может входить)"}

    def clean_new_password(self):
        pwd = self.cleaned_data.get("new_password") or ""
        if pwd and len(pwd) < 8:
            raise forms.ValidationError("Пароль должен быть не короче 8 символов.")
        return pwd


class CourseAccessForm(forms.Form):
    courses = CourseAccessField(
        label="Курсы, доступные студенту", queryset=Course.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["courses"].queryset = _course_choices()
