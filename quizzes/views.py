from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.roles import learner_only
from courses.models import Level
from learning.services import build_course_state, get_enrollment

from .models import QuizAttempt
from .services import grade_attempt


def _quiz_guard(request, level):
    """Возвращает redirect, если тест сейчас недоступен, иначе None."""
    course = level.course
    if not get_enrollment(request.user, course):
        messages.info(request, "У вас нет доступа к этому курсу. Его выдаёт администратор.")
        return redirect(course.get_absolute_url())
    state = build_course_state(request.user, course)
    level_state = state.state_for_level(level.pk)
    if not level_state.unlocked:
        messages.warning(request, "Этот уровень пока закрыт.")
        return redirect(course.get_absolute_url())
    if not level_state.has_quiz:
        return redirect(course.get_absolute_url())
    if not level_state.all_lessons_watched:
        messages.warning(request, "Тест откроется, когда вы просмотрите все уроки уровня.")
        return redirect(course.get_absolute_url())
    return None


@login_required
@learner_only
def take_quiz(request, level_id):
    """Ф-9. Тест в конце уровня. Ответы проверяются на сервере."""
    level = get_object_or_404(Level.objects.select_related("course"), pk=level_id, course__is_published=True)
    blocked = _quiz_guard(request, level)
    if blocked:
        return blocked
    # В шаблон передаём только текст вопросов и вариантов — без признака правильности
    questions = [
        {"id": q.pk, "text": q.text, "choices": [{"id": c.pk, "text": c.text} for c in q.choices.all()]}
        for q in level.questions.prefetch_related("choices")
    ]
    errors = False
    selected = {}
    if request.method == "POST":
        valid_choice_ids = {q["id"]: {c["id"] for c in q["choices"]} for q in questions}
        for q in questions:
            raw = request.POST.get(f"q{q['id']}")
            if raw and raw.isdigit() and int(raw) in valid_choice_ids[q["id"]]:
                selected[q["id"]] = int(raw)
        if len(selected) < len(questions):
            errors = True
            messages.error(request, "Ответьте на все вопросы, прежде чем отправлять тест.")
        else:
            attempt, course_completed = grade_attempt(request.user, level, selected)
            if course_completed:
                request.session["course_completed"] = level.course_id
            return redirect("quizzes:result", attempt_id=attempt.pk)
    return render(
        request,
        "quizzes/take_quiz.html",
        {"level": level, "course": level.course, "questions": questions, "selected": selected, "errors": errors},
    )


@login_required
@learner_only
def my_tests(request):
    """Отдельный раздел «Тесты»: все тесты доступных курсов, их статус и лучший результат."""
    from django.db.models import Count

    attempts_count = dict(
        QuizAttempt.objects.filter(user=request.user).values("level").annotate(n=Count("pk")).values_list("level", "n")
    )
    groups = []
    for enrollment in request.user.enrollments.select_related("course").filter(course__is_published=True):
        state = build_course_state(request.user, enrollment.course, enrollment)
        tests = []
        for ls in state.levels:
            if not ls.has_quiz:
                continue
            if ls.quiz_passed:
                status = "passed"
            elif ls.quiz_available:
                status = "available"
            elif ls.unlocked:
                status = "lessons"
            else:
                status = "locked"
            tests.append({"state": ls, "status": status, "attempts": attempts_count.get(ls.level.pk, 0)})
        if tests:
            groups.append({"course": enrollment.course, "tests": tests})
    return render(request, "quizzes/my_tests.html", {"groups": groups})


@login_required
def quiz_result(request, attempt_id):
    """Ф-10/Ф-11. Результат теста и переход на следующий уровень."""
    attempt = get_object_or_404(QuizAttempt.objects.select_related("level__course"), pk=attempt_id, user=request.user)
    level = attempt.level
    state = build_course_state(request.user, level.course)
    next_level_state = None
    found = False
    for item in state.levels:
        if found:
            next_level_state = item
            break
        found = item.level.pk == level.pk
    just_completed = request.session.pop("course_completed", None) == level.course_id
    course_completed = just_completed or bool(
        attempt.passed and next_level_state is None and state.enrollment and state.enrollment.is_completed
    )
    return render(
        request,
        "quizzes/result.html",
        {
            "attempt": attempt,
            "level": level,
            "course": level.course,
            "state": state,
            "next_level_state": next_level_state,
            "course_completed": course_completed,
        },
    )
