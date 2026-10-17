import re

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

VIDEO_EXTENSIONS = ["mp4", "webm", "mov", "m4v"]
MATERIAL_EXTENSIONS = ["pdf", "ppt", "pptx", "doc", "docx", "xls", "xlsx", "mp3", "wav", "ogg", "m4a", "zip", "txt"]


class Category(models.Model):
    name = models.CharField("название", max_length=100, unique=True)
    order = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Course(models.Model):
    class Difficulty(models.TextChoices):
        BEGINNER = "beginner", "С нуля"
        INTERMEDIATE = "intermediate", "Средний"
        ADVANCED = "advanced", "Продвинутый"

    title = models.CharField("название", max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="courses", verbose_name="категория"
    )
    difficulty = models.CharField("сложность", max_length=20, choices=Difficulty.choices, default=Difficulty.BEGINNER)
    short_description = models.CharField("кратко", max_length=300, blank=True)
    description = models.TextField("описание", blank=True)
    cover = models.ImageField(
        "обложка",
        upload_to="covers/",
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    price = models.DecimalField(
        "цена, сом", max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        help_text="0 — бесплатно. Оплаты на сайте нет: доступ выдаёт администратор.",
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

    @property
    def is_free(self):
        return not self.price


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


class LibraryItem(models.Model):
    """Материал из общей библиотеки администратора: видео или файл, который подключается к урокам."""

    class Kind(models.TextChoices):
        VIDEO = "video", "Видео"
        FILE = "file", "Файл"

    title = models.CharField("название", max_length=200)
    kind = models.CharField("тип", max_length=10, choices=Kind.choices, editable=False, default=Kind.FILE)
    file = models.FileField(
        "файл",
        upload_to="library/",
        validators=[FileExtensionValidator(VIDEO_EXTENSIONS + MATERIAL_EXTENSIONS)],
    )
    description = models.TextField("описание", blank=True)
    uploaded_at = models.DateTimeField("загружен", auto_now_add=True)

    class Meta:
        verbose_name = "материал библиотеки"
        verbose_name_plural = "библиотека материалов"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.kind = self.Kind.VIDEO if self.extension in VIDEO_EXTENSIONS else self.Kind.FILE
        super().save(*args, **kwargs)

    @property
    def filename(self):
        return self.file.name.rsplit("/", 1)[-1]

    @property
    def extension(self):
        return self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""


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
    library_video = models.ForeignKey(
        LibraryItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_lessons",
        limit_choices_to={"kind": "video"},
        verbose_name="видео из библиотеки",
    )
    library_materials = models.ManyToManyField(
        LibraryItem, blank=True, related_name="material_lessons", verbose_name="материалы из библиотеки"
    )

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
    def video_source(self):
        """Загруженный файл урока или видео из библиотеки."""
        if self.video_file:
            return self.video_file
        if self.library_video_id and self.library_video.file:
            return self.library_video.file
        return None

    @property
    def has_video(self):
        return bool(self.video_file or self.video_url or self.library_video_id)


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
