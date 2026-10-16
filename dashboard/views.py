"""Э5. Панель администратора: курсы, уровни, уроки, тесты, пользователи, прогресс."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from community.models import Notification
from courses.models import Category, Course, Lesson, Level
from learning.models import Certificate, Enrollment
from learning.services import build_course_state
from quizzes.models import Question, QuizAttempt

from .forms import CategoryForm, ChoiceFormSet, CourseForm, LessonForm, LevelForm, MaterialFormSet, QuestionForm

User = get_user_model()


def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def announce_course(course):
    """Уведомление всем обучающимся о новом опубликованном курсе (один раз на курс)."""
    url = course.get_absolute_url()
    if Notification.objects.filter(kind=Notification.Kind.NEW_COURSE, url=url).exists():
        return
    Notification.objects.bulk_create(
        Notification(user=u, kind=Notification.Kind.NEW_COURSE, text=f"Новый курс: «{course.title}»", url=url)
        for u in User.objects.filter(is_active=True, is_staff=False).only("pk")
    )


@staff_required
def index(request):
    stats = {
        "courses": Course.objects.count(),
        "published": Course.objects.filter(is_published=True).count(),
        "users": User.objects.filter(is_staff=False).count(),
        "enrollments": Enrollment.objects.count(),
        "completed": Enrollment.objects.filter(completed_at__isnull=False).count(),
        "certificates": Certificate.objects.count(),
    }
    recent_attempts = QuizAttempt.objects.select_related("user", "level__course")[:8]
    recent_users = User.objects.filter(is_staff=False)[:6]
    return render(
        request,
        "dashboard/index.html",
        {"stats": stats, "recent_attempts": recent_attempts, "recent_users": recent_users},
    )


# ---------- А-1. Курсы ----------
@staff_required
def course_list(request):
    courses = Course.objects.annotate(
        levels_total=Count("levels", distinct=True),
        lessons_total=Count("levels__lessons", distinct=True),
        students=Count("enrollments", distinct=True),
    )
    return render(request, "dashboard/course_list.html", {"courses": courses})


@staff_required
def course_create(request):
    form = CourseForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        course = form.save()
        if course.is_published:
            announce_course(course)
        messages.success(request, "Курс создан. Теперь добавьте уровни.")
        return redirect("dashboard:course_edit", pk=course.pk)
    return render(request, "dashboard/course_form.html", {"form": form})


@staff_required
def course_edit(request, pk):
    course = get_object_or_404(Course, pk=pk)
    form = CourseForm(request.POST or None, request.FILES or None, instance=course)
    was_published = course.is_published
    if request.method == "POST" and form.is_valid():
        form.save()
        if course.is_published and not was_published:
            announce_course(course)
        messages.success(request, "Курс сохранён.")
        return redirect("dashboard:course_edit", pk=course.pk)
    levels = course.levels.annotate(
        lessons_total=Count("lessons", distinct=True), questions_total=Count("questions", distinct=True)
    )
    return render(
        request, "dashboard/course_form.html", {"form": form, "course": course, "levels": levels, "level_form": LevelForm(initial={"order": levels.count() + 1})}
    )


@staff_required
@require_POST
def course_toggle_publish(request, pk):
    course = get_object_or_404(Course, pk=pk)
    course.is_published = not course.is_published
    course.save(update_fields=["is_published", "updated_at"])
    if course.is_published:
        announce_course(course)
    messages.success(request, "Курс опубликован." if course.is_published else "Курс скрыт из каталога.")
    return redirect(request.POST.get("next") or "dashboard:course_list")


@staff_required
def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == "POST":
        title = course.title
        course.delete()
        messages.success(request, f"Курс «{title}» удалён.")
        return redirect("dashboard:course_list")
    return render(request, "dashboard/confirm_delete.html", {"object": course, "kind": "курс", "back": "dashboard:course_edit", "back_pk": course.pk})


# ---------- А-2. Уровни ----------
@staff_required
@require_POST
def level_create(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    form = LevelForm(request.POST)
    if form.is_valid():
        level = form.save(commit=False)
        level.course = course
        level.save()
        messages.success(request, f"Уровень «{level.title}» добавлен.")
        return redirect("dashboard:level_edit", pk=level.pk)
    messages.error(request, "Проверьте поля уровня: " + "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("dashboard:course_edit", pk=course.pk)


@staff_required
def level_edit(request, pk):
    level = get_object_or_404(Level.objects.select_related("course"), pk=pk)
    form = LevelForm(request.POST or None, instance=level)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Уровень сохранён.")
        return redirect("dashboard:level_edit", pk=level.pk)
    questions = level.questions.prefetch_related("choices")
    return render(
        request,
        "dashboard/level_form.html",
        {"form": form, "level": level, "course": level.course, "lessons": level.lessons.all(), "questions": questions},
    )


@staff_required
def level_delete(request, pk):
    level = get_object_or_404(Level, pk=pk)
    course_pk = level.course_id
    if request.method == "POST":
        level.delete()
        messages.success(request, "Уровень удалён.")
        return redirect("dashboard:course_edit", pk=course_pk)
    return render(request, "dashboard/confirm_delete.html", {"object": level, "kind": "уровень", "back": "dashboard:level_edit", "back_pk": level.pk})


# ---------- А-3. Уроки ----------
@staff_required
def lesson_form(request, level_pk=None, pk=None):
    lesson = get_object_or_404(Lesson.objects.select_related("level__course"), pk=pk) if pk else None
    level = lesson.level if lesson else get_object_or_404(Level.objects.select_related("course"), pk=level_pk)
    initial = {} if lesson else {"order": level.lessons.count() + 1}
    form = LessonForm(request.POST or None, request.FILES or None, instance=lesson, initial=initial)
    formset = MaterialFormSet(request.POST or None, request.FILES or None, instance=lesson or Lesson(level=level), prefix="materials")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.level = level
            obj.save()
            formset.instance = obj
            formset.save()
        messages.success(request, "Урок сохранён.")
        return redirect("dashboard:lesson_edit", pk=obj.pk)
    return render(
        request,
        "dashboard/lesson_form.html",
        {"form": form, "formset": formset, "lesson": lesson, "level": level, "course": level.course},
    )


@staff_required
def lesson_delete(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    level_pk = lesson.level_id
    if request.method == "POST":
        lesson.delete()
        messages.success(request, "Урок удалён.")
        return redirect("dashboard:level_edit", pk=level_pk)
    return render(request, "dashboard/confirm_delete.html", {"object": lesson, "kind": "урок", "back": "dashboard:lesson_edit", "back_pk": lesson.pk})


# ---------- А-4. Конструктор тестов ----------
@staff_required
def question_form(request, level_pk=None, pk=None):
    question = get_object_or_404(Question.objects.select_related("level__course"), pk=pk) if pk else None
    level = question.level if question else get_object_or_404(Level.objects.select_related("course"), pk=level_pk)
    initial = {} if question else {"order": level.questions.count() + 1}
    form = QuestionForm(request.POST or None, instance=question, initial=initial)
    formset = ChoiceFormSet(request.POST or None, instance=question or Question(level=level), prefix="choices")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.level = level
            obj.save()
            formset.instance = obj
            formset.save()
        messages.success(request, "Вопрос сохранён.")
        if "add_another" in request.POST:
            return redirect("dashboard:question_create", level_pk=level.pk)
        return redirect("dashboard:level_edit", pk=level.pk)
    return render(
        request,
        "dashboard/question_form.html",
        {"form": form, "formset": formset, "question": question, "level": level, "course": level.course},
    )


@staff_required
@require_POST
def question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk)
    level_pk = question.level_id
    question.delete()
    messages.success(request, "Вопрос удалён.")
    return redirect("dashboard:level_edit", pk=level_pk)


# ---------- А-5. Пользователи ----------
@staff_required
def user_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    users = User.objects.annotate(courses_total=Count("enrollments", distinct=True)).order_by("-date_joined")
    if status == "blocked":
        users = users.filter(is_active=False)
    elif status == "active":
        users = users.filter(is_active=True)
    elif status == "staff":
        users = users.filter(is_staff=True)
    if query:
        if connection.vendor == "sqlite":
            needle = query.casefold()
            ids = [u.pk for u in users if needle in u.full_name.casefold() or needle in u.email.casefold()]
            users = users.filter(pk__in=ids)
        else:
            users = users.filter(Q(full_name__icontains=query) | Q(email__icontains=query))
    page = Paginator(users, 25).get_page(request.GET.get("page"))
    return render(request, "dashboard/user_list.html", {"page": page, "query": query, "status": status})


@staff_required
@require_POST
def user_toggle_block(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user or target.is_superuser:
        messages.error(request, "Нельзя заблокировать себя или суперпользователя.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        messages.success(request, f"{target.full_name}: " + ("разблокирован." if target.is_active else "заблокирован."))
    return redirect(request.POST.get("next") or "dashboard:user_list")


# ---------- А-6. Прогресс пользователей ----------
@staff_required
def user_detail(request, pk):
    target = get_object_or_404(User, pk=pk)
    enrollments = target.enrollments.select_related("course")
    items = [build_course_state(target, e.course, e) for e in enrollments]
    attempts = QuizAttempt.objects.filter(user=target).select_related("level__course")[:30]
    return render(request, "dashboard/user_detail.html", {"target": target, "items": items, "attempts": attempts})


# ---------- Категории курсов ----------
@staff_required
def categories(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST":
        delete_id = request.POST.get("delete")
        if delete_id and delete_id.isdigit():
            Category.objects.filter(pk=delete_id).delete()
            messages.success(request, "Категория удалена. Курсы остались без категории.")
            return redirect("dashboard:categories")
        if form.is_valid():
            form.save()
            messages.success(request, "Категория добавлена.")
            return redirect("dashboard:categories")
    items = Category.objects.annotate(total=Count("courses"))
    return render(request, "dashboard/categories.html", {"form": form, "items": items})
