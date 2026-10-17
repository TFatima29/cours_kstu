from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from accounts.roles import learner_only
from quizzes.models import QuizAttempt

from .models import Certificate
from .services import build_course_state


@login_required
@learner_only
def my_courses(request):
    """Ф-6. «Мои курсы» — курсы, на которые записан пользователь."""
    enrollments = request.user.enrollments.select_related("course").all()
    items = [build_course_state(request.user, e.course, e) for e in enrollments]
    return render(request, "learning/my_courses.html", {"items": items})


@login_required
@learner_only
def my_progress(request):
    """Ф-14. Процент прохождения по каждому курсу и результаты тестов."""
    enrollments = request.user.enrollments.select_related("course").all()
    items = [build_course_state(request.user, e.course, e) for e in enrollments]
    attempts = QuizAttempt.objects.filter(user=request.user).select_related("level__course")[:50]
    total_done = sum(1 for s in items if s.enrollment.is_completed)
    passed_tests = QuizAttempt.objects.filter(user=request.user, passed=True).values("level").distinct().count()
    return render(
        request,
        "learning/progress.html",
        {"items": items, "attempts": attempts, "total_done": total_done, "passed_tests": passed_tests},
    )


def certificate(request, number):
    """Ф-12. Сертификат о прохождении курса (страница для печати / PDF). Доступен по номеру для проверки."""
    cert = get_object_or_404(Certificate.objects.select_related("enrollment__user", "enrollment__course"), number=number)
    return render(request, "learning/certificate.html", {"cert": cert})


def verify_certificate(request):
    """Проверка подлинности сертификата по номеру (полному или короткому)."""
    number = request.GET.get("number", "").strip().lower()
    cert = None
    checked = bool(number)
    if number:
        qs = Certificate.objects.select_related("enrollment__user", "enrollment__course")
        if len(number) == 36:
            cert = qs.filter(number=number).first()
        elif len(number) == 8:
            cert = next((c for c in qs if str(c.number).startswith(number)), None)
    return render(request, "learning/verify.html", {"cert": cert, "checked": checked, "number": number})
