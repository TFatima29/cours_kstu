from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from courses.models import Lesson
from learning.services import get_enrollment, is_lesson_available

from .context_processors import THEMES
from .models import Comment, Notification, notify


@login_required
@require_POST
def add_comment(request, lesson_pk):
    lesson = get_object_or_404(Lesson.objects.select_related("level__course"), pk=lesson_pk)
    allowed = request.user.is_staff or (
        get_enrollment(request.user, lesson.level.course) and is_lesson_available(request.user, lesson)
    )
    if not allowed:
        messages.error(request, "Комментировать можно только открытые уроки своих курсов.")
        return redirect(lesson.level.course.get_absolute_url())
    text = request.POST.get("text", "").strip()
    if not text:
        messages.error(request, "Напишите текст комментария.")
    elif len(text) > 2000:
        messages.error(request, "Комментарий длиннее 2000 символов.")
    else:
        parent = None
        parent_id = request.POST.get("parent")
        if parent_id and parent_id.isdigit():
            parent = Comment.objects.filter(pk=parent_id, lesson=lesson, parent__isnull=True).first()
        comment = Comment.objects.create(lesson=lesson, user=request.user, text=text, parent=parent)
        if parent and parent.user_id != request.user.pk:
            notify(
                parent.user,
                Notification.Kind.REPLY,
                f"{request.user.get_short_name()} ответил(а) на ваш комментарий к уроку «{lesson.title}»",
                f"{lesson.get_absolute_url()}#comment-{comment.pk}",
            )
        return redirect(f"{lesson.get_absolute_url()}#comment-{comment.pk}")
    return redirect(f"{lesson.get_absolute_url()}#comments")


@login_required
@require_POST
def delete_comment(request, pk):
    """Автор удаляет свой комментарий, администратор — скрывает любой."""
    comment = get_object_or_404(Comment.objects.select_related("lesson"), pk=pk)
    if comment.user_id == request.user.pk:
        comment.delete()
        messages.success(request, "Комментарий удалён.")
    elif request.user.is_staff:
        comment.is_hidden = not comment.is_hidden
        comment.save(update_fields=["is_hidden"])
        messages.success(request, "Комментарий скрыт." if comment.is_hidden else "Комментарий снова виден.")
    else:
        messages.error(request, "Можно удалять только свои комментарии.")
    return redirect(f"{comment.lesson.get_absolute_url()}#comments")


@login_required
def notifications(request):
    items = list(request.user.notifications.all()[:50])
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "community/notifications.html", {"items": items})


@login_required
def open_notification(request, pk):
    item = get_object_or_404(Notification, pk=pk, user=request.user)
    if not item.is_read:
        item.is_read = True
        item.save(update_fields=["is_read"])
    return redirect(item.url or "community:notifications")


@require_POST
def set_theme(request):
    """Переключение варианта оформления (хранится в сессии)."""
    theme = request.POST.get("theme")
    if theme in THEMES:
        request.session["site_theme"] = theme
    back = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
        back = "/"
    return redirect(back)
