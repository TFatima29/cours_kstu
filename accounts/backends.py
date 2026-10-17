"""Вход по e-mail или по логину, который выдал администратор."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrLoginBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        username = (username or kwargs.get(get_user_model().USERNAME_FIELD) or "").strip()
        if not username or password is None:
            return None
        user = find_user(username)
        if user is None:
            get_user_model()().set_password(password)  # одинаковое время ответа для несуществующих
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


def find_user(username):
    """Пользователь по e-mail или логину (без учёта регистра)."""
    username = (username or "").strip()
    if not username:
        return None
    return get_user_model().objects.filter(Q(email__iexact=username) | Q(login__iexact=username)).first()
