"""Выдача учётных записей администратором: пароль генерируется и отправляется пользователю на e-mail."""
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
        f"Логин (e-mail): {user.email}",
        f"Пароль: {password}",
        "",
        "После входа пароль можно сменить в профиле.",
    ]
    try:
        send_mail(subject, "\n".join(lines), settings.DEFAULT_FROM_EMAIL, [user.email])
        return True
    except Exception:  # почтовый сервер недоступен — администратор увидит пароль на экране
        return False
