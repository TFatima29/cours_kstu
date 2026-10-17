from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Count
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.roles import learner_only
from learning.services import build_course_state, get_enrollment, is_lesson_available, mark_lesson_watched

from .models import Category, Course, Lesson, LibraryItem, Material


def visible_courses(user):
    qs = Course.objects.all()
    if not (user.is_authenticated and user.is_staff):
        qs = qs.filter(is_published=True)
    return qs


@learner_only
def catalog(request):
    """Ф-4. Каталог всех опубликованных курсов с ценами.

    Оплаты на сайте нет: видны все курсы, а открыть уроки можно только тех, к которым доступ выдал администратор.
    """
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    difficulty = request.GET.get("level", "")
    base = Course.objects.filter(is_published=True)
    courses = (
        base
        .select_related("category")
        .annotate(levels_total=Count("levels", distinct=True), lessons_total=Count("levels__lessons", distinct=True))
        .order_by("-created_at")
    )
    if category.isdigit():
        courses = courses.filter(category_id=int(category))
    if difficulty in Course.Difficulty.values:
        courses = courses.filter(difficulty=difficulty)
    if query:
        if connection.vendor == "sqlite":
            # SQLite сравнивает без учёта регистра только латиницу — для кириллицы ищем в Python
            needle = query.casefold()
            courses = [c for c in courses if needle in c.title.casefold()]
        else:
            courses = courses.filter(title__icontains=query)
    enrolled_ids = set()
    if request.user.is_authenticated:
        enrolled_ids = set(request.user.enrollments.values_list("course_id", flat=True))
    return render(
        request,
        "courses/catalog.html",
        {
            "courses": courses,
            "query": query,
            "enrolled_ids": enrolled_ids,
            "categories": Category.objects.filter(courses__in=base).distinct(),
            "difficulties": Course.Difficulty.choices,
            "active_category": category,
            "active_level": difficulty,
            "filtered": bool(query or category or difficulty),
            "hero_courses": _hero_courses(base),
            "stats": {
                "courses": base.count(),
                "lessons": Lesson.objects.filter(level__course__in=base).count(),
            },
        },
    )


def course_detail(request, pk):
    """Ф-5. Карточка курса: описание, уровни и уроки, кнопка «Записаться»."""
    course = get_object_or_404(visible_courses(request.user), pk=pk)
    state = build_course_state(request.user, course)
    return render(
        request,
        "courses/course_detail.html",
        {"course": course, "state": state, "recent_comments": _course_comments(request.user, course) if state.enrollment else []},
    )


@login_required
@learner_only
@require_POST
def enroll(request, pk):
    """Ф-6. Самостоятельной записи нет: доступ к курсу выдаёт администратор."""
    messages.info(request, "Доступ к курсам выдаёт администратор платформы.")
    return redirect("learning:my_courses")


@login_required
def lesson_detail(request, pk):
    """Ф-7. Урок: видео, описание, материалы."""
    lesson = get_object_or_404(Lesson.objects.select_related("level__course"), pk=pk)
    course = lesson.level.course
    if not course.is_published and not request.user.is_staff:
        raise Http404
    if not request.user.is_staff and not get_enrollment(request.user, course):
        messages.info(request, "У вас нет доступа к этому курсу. Его выдаёт администратор.")
        return redirect(course.get_absolute_url())
    state = build_course_state(request.user, course)
    level_state = state.state_for_level(lesson.level_id)
    if not request.user.is_staff and not level_state.unlocked:
        messages.warning(request, "Этот уровень пока закрыт: завершите предыдущий уровень и сдайте тест.")
        return redirect(course.get_absolute_url())

    # соседние уроки для навигации
    ordered = [item.lesson for lv in state.levels for item in lv.lessons]
    index = next(i for i, item in enumerate(ordered) if item.pk == lesson.pk)
    prev_lesson = ordered[index - 1] if index > 0 else None
    next_lesson = ordered[index + 1] if index + 1 < len(ordered) else None
    if next_lesson and next_lesson.level_id != lesson.level_id:
        next_state = state.state_for_level(next_lesson.level_id)
        if not (next_state and next_state.unlocked) and not request.user.is_staff:
            next_lesson = None
    watched = any(item.watched for item in level_state.lessons if item.lesson.pk == lesson.pk)
    return render(
        request,
        "courses/lesson_detail.html",
        {
            "lesson": lesson,
            "course": course,
            "state": state,
            "level_state": level_state,
            "watched": watched,
            "prev_lesson": prev_lesson,
            "next_lesson": next_lesson,
            "materials": lesson.materials.all(),
            "library_materials": lesson.library_materials.filter(kind=LibraryItem.Kind.FILE),
            "comments": _lesson_comments(request.user, lesson),
            "can_comment": bool(state.enrollment) or request.user.is_staff,
        },
    )


@login_required
@require_POST
def lesson_watched(request, pk):
    """Ф-8. Отметка о просмотре: вызывается страницей урока после 90% видео."""
    lesson = get_object_or_404(Lesson.objects.select_related("level__course"), pk=pk)
    if not get_enrollment(request.user, lesson.level.course) or not is_lesson_available(request.user, lesson):
        return JsonResponse({"ok": False, "error": "Урок недоступен"}, status=403)
    course_completed = mark_lesson_watched(request.user, lesson)
    state = build_course_state(request.user, lesson.level.course)
    level_state = state.state_for_level(lesson.level_id)
    data = {
        "ok": True,
        "percent": state.percent,
        "level_lessons_done": level_state.all_lessons_watched,
        "quiz_available": level_state.quiz_available and not level_state.quiz_passed,
        "course_completed": course_completed,
    }
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse(data)
    messages.success(request, "Урок отмечен как просмотренный.")
    return redirect(lesson.get_absolute_url())


@login_required
def material_download(request, pk):
    """Скачивание материала — только для тех, кому открыт урок."""
    material = get_object_or_404(Material.objects.select_related("lesson__level__course"), pk=pk)
    lesson = material.lesson
    if not request.user.is_staff:
        if not get_enrollment(request.user, lesson.level.course) or not is_lesson_available(request.user, lesson):
            raise Http404
    return FileResponse(material.file.open("rb"), as_attachment=True, filename=material.filename)


@login_required
def library_download(request, lesson_pk, pk):
    """Скачивание файла из библиотеки, подключённого к уроку."""
    lesson = get_object_or_404(Lesson.objects.select_related("level__course"), pk=lesson_pk)
    item = get_object_or_404(lesson.library_materials, pk=pk)
    if not request.user.is_staff:
        if not get_enrollment(request.user, lesson.level.course) or not is_lesson_available(request.user, lesson):
            raise Http404
    return FileResponse(item.file.open("rb"), as_attachment=True, filename=item.filename)


def _course_comments(user, course, limit=8):
    """Последние комментарии по всем урокам курса — для страницы курса."""
    from community.models import Comment

    qs = Comment.objects.select_related("user", "lesson").filter(lesson__level__course=course)
    if not user.is_staff:
        qs = qs.filter(is_hidden=False)
    return qs.order_by("-created_at")[:limit]


def _lesson_comments(user, lesson):
    from django.db.models import Prefetch

    from community.models import Comment

    visible = Comment.objects.select_related("user")
    if not user.is_staff:
        visible = visible.filter(is_hidden=False)
    return (
        visible.filter(lesson=lesson, parent__isnull=True)
        .prefetch_related(Prefetch("replies", queryset=visible.order_by("created_at")))
        .order_by("created_at")
    )


def _hero_courses(base=None):
    """Данные для интерактивного героя каталога: название, ссылка, число уроков и уровней."""
    base = Course.objects.filter(is_published=True) if base is None else base
    rows = (
        base
        .annotate(lessons_total=Count("levels__lessons", distinct=True), levels_total=Count("levels", distinct=True))
        .order_by("-lessons_total", "-created_at")[:12]
    )
    rows = rows.prefetch_related("levels__lessons")
    return [
        {
            "id": c.pk,
            "title": c.title,
            "url": c.get_absolute_url(),
            "lessons": c.lessons_total,
            "levels": c.levels_total,
            "sectors": [{"title": lv.title, "lessons": len(lv.lessons.all())} for lv in c.levels.all()],
        }
        for c in rows
    ]
