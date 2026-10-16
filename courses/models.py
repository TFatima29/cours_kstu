import re

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

VIDEO_EXTENSIONS = ["mp4", "webm", "mov", "m4v"]
MATERIAL_EXTENSIONS = ["pdf", "ppt", "pptx", "doc", "docx", "xls", "xlsx", "mp3", "wav", "ogg", "m4a", "zip", "txt"]


class Course(models.Model):
    title = models.CharField("название", max_length=200)
    short_description = models.CharField("кратко", max_length=300, blank=True)
    description = models.TextField("описание", blank=True)
    cover = models.ImageField(
        "обложка",
        upload_to="covers/",
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    is_published = models.BooleanField("опубликован", default=False)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "курс"
        verbose_name_plural = "курсы"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:detail", args=[self.pk])

    @property
    def lessons_count(self):
        return Lesson.objects.filter(level__course=self).count()


class Level(models.Model):
    """Уровень (модуль) курса. Завершается тестом."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="levels", verbose_name="курс")
    title = models.CharField("название", max_length=200)
    order = models.PositiveIntegerField("порядок", default=1)
    pass_threshold = models.PositiveSmallIntegerField(
        "порог прохождения теста, %",
        default=settings.PASS_THRESHOLD_DEFAULT,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )

    class Meta:
        verbose_name = "уровень"
        verbose_name_plural = "уровни"
        ordering = ["course", "order", "pk"]

    def __str__(self):
        return f"{self.course} — {self.title}"

    @property
    def has_quiz(self):
        return self.questions.exists()

    def previous(self):
        return (
            self.course.levels.filter(models.Q(order__lt=self.order) | models.Q(order=self.order, pk__lt=self.pk))
            .order_by("-order", "-pk")
            .first()
        )


YOUTUBE_RE = re.compile(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")


class Lesson(models.Model):
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="lessons", verbose_name="уровень")
    title = models.CharField("название", max_length=200)
    order = models.PositiveIntegerField("порядок", default=1)
    description = models.TextField("описание", blank=True)
    video_file = models.FileField(
        "видео (файл)",
        upload_to="videos/",
        blank=True,
        validators=[FileExtensionValidator(VIDEO_EXTENSIONS)],
    )
    video_url = models.URLField("видео (ссылка)", blank=True, help_text="YouTube или прямая ссылка на mp4")

    class Meta:
        verbose_name = "урок"
        verbose_name_plural = "уроки"
        ordering = ["level", "order", "pk"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:lesson", args=[self.pk])

    @property
    def course(self):
        return self.level.course

    @property
    def youtube_id(self):
        if not self.video_url:
            return None
        m = YOUTUBE_RE.search(self.video_url)
        return m.group(1) if m else None

    @property
    def has_video(self):
        return bool(self.video_file or self.video_url)


class Material(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="materials", verbose_name="урок")
    title = models.CharField("название", max_length=200, blank=True)
    file = models.FileField(
        "файл",
        upload_to="materials/",
        validators=[FileExtensionValidator(MATERIAL_EXTENSIONS)],
    )

    class Meta:
        verbose_name = "материал"
        verbose_name_plural = "материалы"

    def __str__(self):
        return self.title or self.filename

    @property
    def filename(self):
        return self.file.name.rsplit("/", 1)[-1]

    @property
    def extension(self):
        return self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""
