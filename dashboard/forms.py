from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from courses.models import Course, Lesson, Level, Material
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
        fields = ["title", "short_description", "description", "cover", "is_published"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "cover": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }

    def clean_cover(self):
        return _check_size(self.cleaned_data.get("cover"), MAX_COVER_MB)


class LevelForm(forms.ModelForm):
    class Meta:
        model = Level
        fields = ["title", "order", "pass_threshold"]


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title", "order", "description", "video_file", "video_url"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "video_file": forms.ClearableFileInput(attrs={"accept": "video/mp4,video/webm,video/quicktime"}),
        }

    def clean_video_file(self):
        return _check_size(self.cleaned_data.get("video_file"), MAX_VIDEO_MB)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("video_file") and cleaned.get("video_url"):
            self.add_error("video_url", "Укажите что-то одно: файл видео или ссылку.")
        return cleaned


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ["title", "file"]

    def clean_file(self):
        return _check_size(self.cleaned_data.get("file"), MAX_MATERIAL_MB)


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
