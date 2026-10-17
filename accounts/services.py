"""Выдача учётных записей администратором: пароль генерируется и отправляется пользователю на e-mail."""
import re
import secrets
import string

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

ALPHABET = string.ascii_letters + string.digits


def generate_password(length=10):
    """Случайный пароль без похожих символов (l, I, O, 0), обязательно с буквами и цифрами."""
    alphabet = "".join(ch for ch in ALPHABET if ch not in "lIO0")
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in pwd) and any(c.isalpha() for c in pwd):
            return pwd


LOGIN_RE = re.compile(r"^[A-Za-z0-9._-]{3,50}$")


def generate_login(email):
    """Логин из части e-mail до «@»; если занят — добавляем цифры."""
    from .models import User

    base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower())[:40] or "student"
    if len(base) < 3:
        base = f"{base}user"
    candidate = base
    while User.objects.filter(login__iexact=candidate).exists():
        candidate = f"{base}{secrets.randbelow(9000) + 1000}"
    return candidate


def send_credentials(request, user, password, is_new=True):
    """Отправляет логин и пароль на почту пользователя. Возвращает True, если письмо ушло."""
    login_url = request.build_absolute_uri(reverse("accounts:login"))
    subject = "Доступ к Course Platform" if is_new else "Новый пароль для Course Platform"
    lines = [
        f"Здравствуйте, {user.full_name}!",
        "",
        "Администратор создал для вас учётную запись на платформе онлайн-обучения Course Platform."
        if is_new else "Администратор выдал вам новый пароль для входа на Course Platform.",
        "",
        f"Адрес для входа: {login_url}",
        f"Логин: {user.login or user.email}",
        f"E-mail (тоже подходит для входа): {user.email}",
        f"Пароль: {password}",
        "",
        "После входа пароль можно сменить в профиле.",
    ]
    if not user.is_staff:
        titles = list(user.enrollments.values_list("course__title", flat=True))
        if titles:
            lines += ["", "Вам открыт доступ к курсам:"] + [f"  — {t}" for t in titles]
    try:
        send_mail(subject, "\n".join(lines), settings.DEFAULT_FROM_EMAIL, [user.email])
        return True
    except Exception:  # почтовый сервер недоступен — администратор увидит пароль на экране
        return False
