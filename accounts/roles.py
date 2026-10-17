"""Разделение интерфейса по ролям.

Обучающийся работает с каталогом, своими курсами и прогрессом.
Администратор работает только в панели администратора: каталог, «Мои курсы» и «Мой прогресс»
ему не нужны — он не учится, а наполняет платформу и следит за пользователями.
"""
from functools import wraps

from django.shortcuts import redirect


def is_admin(user):
    return user.is_authenticated and user.is_staff


def home_url_name(user):
    return "dashboard:index" if is_admin(user) else "learning:my_courses"


def learner_only(view):
    """Страницы обучающегося: администратора отправляем в его панель."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if is_admin(request.user):
            return redirect("dashboard:index")
        return view(request, *args, **kwargs)

    return wrapper
