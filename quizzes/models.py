from django.conf import settings
from django.db import models

from courses.models import Level


class Question(models.Model):
    """Вопрос итогового теста уровня."""

    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="questions", verbose_name="уровень")
    text = models.TextField("вопрос")
    order = models.PositiveIntegerField("порядок", default=1)

    class Meta:
        verbose_name = "вопрос"
        verbose_name_plural = "вопросы"
        ordering = ["level", "order", "pk"]

    def __str__(self):
        return self.text[:80]


class Choice(models.Model):
    """Вариант ответа. Поле is_correct никогда не передаётся в браузер."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices", verbose_name="вопрос")
    text = models.CharField("вариант ответа", max_length=300)
    is_correct = models.BooleanField("правильный", default=False)

    class Meta:
        verbose_name = "вариант ответа"
        verbose_name_plural = "варианты ответа"
        ordering = ["question", "pk"]

    def __str__(self):
        return self.text


class QuizAttempt(models.Model):
    """Попытка прохождения теста."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_attempts")
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="attempts")
    correct = models.PositiveIntegerField("правильных ответов", default=0)
    total = models.PositiveIntegerField("всего вопросов", default=0)
    score = models.PositiveSmallIntegerField("результат, %", default=0)
    passed = models.BooleanField("сдан", default=False)
    created_at = models.DateTimeField("дата", auto_now_add=True)

    class Meta:
        verbose_name = "попытка теста"
        verbose_name_plural = "попытки тестов"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.level}: {self.score}%"
