"""Проверка теста. Выполняется только на сервере: правильные ответы в браузер не уходят."""
from django.db import transaction

from learning.services import complete_course_if_done

from .models import Choice, QuizAttempt


@transaction.atomic
def grade_attempt(user, level, answers):
    """answers: {question_id: choice_id}. Возвращает (attempt, course_completed)."""
    questions = list(level.questions.all())
    correct_ids = set(
        Choice.objects.filter(question__level=level, is_correct=True).values_list("question_id", "pk")
    )
    correct = sum(1 for q in questions if (q.pk, answers.get(q.pk)) in correct_ids)
    total = len(questions)
    score = int(correct * 100 / total) if total else 0  # округление вниз — без «натягивания» оценки
    attempt = QuizAttempt.objects.create(
        user=user,
        level=level,
        correct=correct,
        total=total,
        score=score,
        passed=score >= level.pass_threshold,
    )
    course_completed = attempt.passed and complete_course_if_done(user, level.course)
    return attempt, course_completed
