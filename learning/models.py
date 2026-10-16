import uuid

from django.conf import settings
from django.db import models

from courses.models import Course, Lesson


class Enrollment(models.Model):
    """Запись пользователя на курс (без оплаты)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    enrolled_at = models.DateTimeField("дата записи", auto_now_add=True)
    completed_at = models.DateTimeField("дата завершения", null=True, blank=True)

    class Meta:
        verbose_name = "запись на курс"
        verbose_name_plural = "записи на курсы"
        ordering = ["-enrolled_at"]
        constraints = [models.UniqueConstraint(fields=["user", "course"], name="unique_enrollment")]

    def __str__(self):
        return f"{self.user} → {self.course}"

    @property
    def is_completed(self):
        return self.completed_at is not None


class LessonProgress(models.Model):
    """Отметка о просмотре урока."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress")
    watched_at = models.DateTimeField("просмотрен", auto_now_add=True)

    class Meta:
        verbose_name = "просмотр урока"
        verbose_name_plural = "просмотры уроков"
        constraints = [models.UniqueConstraint(fields=["user", "lesson"], name="unique_lesson_progress")]


class Certificate(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name="certificate")
    number = models.UUIDField("номер", default=uuid.uuid4, unique=True, editable=False)
    issued_at = models.DateTimeField("выдан", auto_now_add=True)

    class Meta:
        verbose_name = "сертификат"
        verbose_name_plural = "сертификаты"

    def __str__(self):
        return f"Сертификат {self.short_number}"

    @property
    def short_number(self):
        return str(self.number).split("-")[0].upper()
