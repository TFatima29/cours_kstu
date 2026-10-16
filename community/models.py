from django.conf import settings
from django.db import models

from courses.models import Lesson


class Comment(models.Model):
    """Комментарий под уроком. parent — ответ на другой комментарий (один уровень вложенности)."""

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="comments", verbose_name="урок")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    text = models.TextField("текст", max_length=2000)
    is_hidden = models.BooleanField("скрыт администратором", default=False)
    created_at = models.DateTimeField("дата", auto_now_add=True)

    class Meta:
        verbose_name = "комментарий"
        verbose_name_plural = "комментарии"
        ordering = ["created_at"]

    def __str__(self):
        return self.text[:60]


class Notification(models.Model):
    class Kind(models.TextChoices):
        LEVEL_UNLOCKED = "level", "Открыт уровень"
        COURSE_COMPLETED = "course", "Курс пройден"
        REPLY = "reply", "Ответ на комментарий"
        NEW_COURSE = "new_course", "Новый курс"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField("тип", max_length=20, choices=Kind.choices)
    text = models.CharField("текст", max_length=300)
    url = models.CharField("ссылка", max_length=300, blank=True)
    is_read = models.BooleanField("прочитано", default=False)
    created_at = models.DateTimeField("дата", auto_now_add=True)

    class Meta:
        verbose_name = "уведомление"
        verbose_name_plural = "уведомления"
        ordering = ["-created_at"]

    def __str__(self):
        return self.text


def notify(user, kind, text, url=""):
    return Notification.objects.create(user=user, kind=kind, text=text, url=url)
