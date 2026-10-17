from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import FileExtensionValidator
from django.db import models


class UserManager(BaseUserManager):
    """Менеджер пользователей: вход по e-mail вместо логина."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Нужно указать e-mail")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)  # пароль сохраняется только в виде хеша
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)


def avatar_path(instance, filename):
    return f"avatars/user_{instance.pk or 'new'}/{filename}"


class User(AbstractUser):
    """Пользователь платформы.

    is_staff = True — администратор платформы.
    is_active = False — пользователь заблокирован и не может войти.
    """

    username = None
    email = models.EmailField("e-mail", unique=True)
    login = models.CharField(
        "логин",
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text="Латинские буквы, цифры, точка, дефис и подчёркивание. Входить можно по логину или e-mail.",
    )
    full_name = models.CharField("имя", max_length=150)
    avatar = models.ImageField(
        "аватар",
        upload_to=avatar_path,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(" ")[0] if self.full_name else self.email

    @property
    def initials(self):
        parts = [p for p in self.full_name.split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or self.email[0].upper()
