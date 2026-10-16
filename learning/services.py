"""Правила прохождения курса.

Курс → уровни → уроки. Уровень завершён, когда просмотрены все его уроки
и сдан тест (если в уровне есть вопросы). Следующий уровень открывается
только после завершения предыдущего. Все проверки выполняются на сервере.
"""
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from courses.models import Course, Lesson, Level
from quizzes.models import Question, QuizAttempt

from .models import Certificate, Enrollment, LessonProgress


@dataclass
class LessonState:
    lesson: Lesson
    watched: bool


@dataclass
class LevelState:
    level: Level
    unlocked: bool
    lessons: list = field(default_factory=list)
    has_quiz: bool = False
    quiz_passed: bool = False
    best_score: int | None = None

    @property
    def lessons_watched(self):
        return sum(1 for item in self.lessons if item.watched)

    @property
    def all_lessons_watched(self):
        return self.lessons_watched == len(self.lessons)

    @property
    def completed(self):
        return self.all_lessons_watched and (self.quiz_passed or not self.has_quiz)

    @property
    def quiz_available(self):
        return self.unlocked and self.has_quiz and self.all_lessons_watched


@dataclass
class CourseState:
    course: Course
    levels: list
    enrollment: Enrollment | None

    @property
    def total_units(self):
        return sum(len(s.lessons) + (1 if s.has_quiz else 0) for s in self.levels)

    @property
    def done_units(self):
        return sum(s.lessons_watched + (1 if s.has_quiz and s.quiz_passed else 0) for s in self.levels)

    @property
    def percent(self):
        if not self.total_units:
            return 0
        return round(self.done_units * 100 / self.total_units)

    @property
    def all_completed(self):
        return bool(self.levels) and all(s.completed for s in self.levels)

    @property
    def next_lesson(self):
        """Первый непросмотренный урок в открытых уровнях — для кнопки «Продолжить»."""
        for state in self.levels:
            if not state.unlocked:
                return None
            for item in state.lessons:
                if not item.watched:
                    return item.lesson
        return None

    @property
    def pending_quiz_level(self):
        for state in self.levels:
            if state.quiz_available and not state.quiz_passed:
                return state.level
        return None

    def state_for_level(self, level_id):
        return next((s for s in self.levels if s.level.pk == level_id), None)


def get_enrollment(user, course):
    if not user.is_authenticated:
        return None
    return Enrollment.objects.filter(user=user, course=course).first()


def build_course_state(user, course, enrollment=None):
    """Собирает состояние всех уровней курса для пользователя за несколько запросов."""
    if enrollment is None:
        enrollment = get_enrollment(user, course)
    levels = list(course.levels.prefetch_related("lessons").all())
    level_ids = [lv.pk for lv in levels]

    watched_ids, passed_ids, best_scores = set(), set(), {}
    quiz_level_ids = set(Question.objects.filter(level_id__in=level_ids).values_list("level_id", flat=True))
    if user.is_authenticated:
        watched_ids = set(
            LessonProgress.objects.filter(user=user, lesson__level__course=course).values_list("lesson_id", flat=True)
        )
        attempts = QuizAttempt.objects.filter(user=user, level_id__in=level_ids)
        passed_ids = set(attempts.filter(passed=True).values_list("level_id", flat=True))
        best_scores = dict(attempts.values("level_id").annotate(best=Max("score")).values_list("level_id", "best"))

    states = []
    previous_completed = enrollment is not None  # первый уровень открыт, если пользователь записан
    for level in levels:
        state = LevelState(
            level=level,
            unlocked=previous_completed,
            lessons=[LessonState(lesson, lesson.pk in watched_ids) for lesson in level.lessons.all()],
            has_quiz=level.pk in quiz_level_ids,
            quiz_passed=level.pk in passed_ids,
            best_score=best_scores.get(level.pk),
        )
        states.append(state)
        previous_completed = state.unlocked and state.completed
    return CourseState(course=course, levels=states, enrollment=enrollment)


def is_lesson_available(user, lesson):
    if user.is_authenticated and user.is_staff:
        return True
    state = build_course_state(user, lesson.level.course)
    level_state = state.state_for_level(lesson.level_id)
    return bool(level_state and level_state.unlocked)


def mark_lesson_watched(user, lesson):
    """Отмечает урок просмотренным и проверяет, не завершён ли курс."""
    LessonProgress.objects.get_or_create(user=user, lesson=lesson)
    return complete_course_if_done(user, lesson.level.course)


@transaction.atomic
def complete_course_if_done(user, course):
    """Ставит отметку «Курс пройден» и выдаёт сертификат. Возвращает True, если курс только что завершён."""
    enrollment = Enrollment.objects.select_for_update().filter(user=user, course=course).first()
    if enrollment is None or enrollment.is_completed:
        return False
    state = build_course_state(user, course, enrollment)
    if not state.all_completed:
        return False
    enrollment.completed_at = timezone.now()
    enrollment.save(update_fields=["completed_at"])
    Certificate.objects.get_or_create(enrollment=enrollment)
    return True
