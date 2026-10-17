from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import AuthenticationForm

from .models import User

MAX_AVATAR_MB = 5


class RegisterForm(forms.ModelForm):
    """Ф-1. Регистрация по имени, e-mail и паролю."""

    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(
        label="Повторите пароль", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )

    class Meta:
        model = User
        fields = ["full_name", "email"]
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Как к вам обращаться"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "name@example.com"}),
        }

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if not name:
            raise forms.ValidationError("Укажите имя.")
        return name

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким e-mail уже зарегистрирован.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Пароли не совпадают.")
        elif p1:
            user = User(email=cleaned.get("email", ""), full_name=cleaned.get("full_name", ""))
            try:
                password_validation.validate_password(p1, user)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Ф-2. Вход по e-mail и паролю. Заблокированным пользователям сообщаем причину."""

    username = forms.CharField(
        label="Логин или e-mail", widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"})
    )

    error_messages = {
        "invalid_login": "Неверный логин или пароль.",
        "inactive": "Аккаунт заблокирован администратором.",
    }

    def clean(self):
        from .backends import find_user

        username = (self.cleaned_data.get("username") or "").strip()
        password = self.cleaned_data.get("password")
        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                blocked = find_user(username)
                if blocked and not blocked.is_active and blocked.check_password(password):
                    raise forms.ValidationError(self.error_messages["inactive"], code="inactive")
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class ProfileForm(forms.ModelForm):
    """Ф-13. Личные данные и аватар."""

    class Meta:
        model = User
        fields = ["full_name", "avatar"]
        widgets = {"avatar": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})}

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "size") and avatar.size > MAX_AVATAR_MB * 1024 * 1024:
            raise forms.ValidationError(f"Файл больше {MAX_AVATAR_MB} МБ.")
        return avatar
