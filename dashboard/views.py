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
from courses.models import Category, Course, Lesson, LibraryItem, Level
from learning.models import Certificate, Enrollment
from learning.services import build_course_state
from quizzes.models import Question, QuizAttempt

from accounts.services import generate_login, generate_password, send_credentials

from .forms import (
    CategoryForm,
    ChoiceFormSet,
    CourseAccessForm,
    CourseForm,
    LessonForm,
    LevelForm,
    LibraryItemForm,
    MaterialFormSet,
    QuestionForm,
    UserCreateForm,
    UserEditForm,
)

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
            form.save_m2m()
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
        users = users.filter(is_active=False, is_staff=False)
    elif status == "active":
        users = users.filter(is_active=True, is_staff=False)
    elif status == "staff":
        users = users.filter(is_staff=True)
    elif status != "all":
        users = users.filter(is_staff=False)  # по умолчанию — студенты
    if query:
        if connection.vendor == "sqlite":
            needle = query.casefold()
            ids = [
                u.pk
                for u in users
                if needle in u.full_name.casefold() or needle in u.email.casefold() or needle in (u.login or "").casefold()
            ]
            users = users.filter(pk__in=ids)
        else:
            users = users.filter(Q(full_name__icontains=query) | Q(email__icontains=query) | Q(login__icontains=query))
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
    issued = request.session.pop("issued_credentials", None)
    if issued and issued.get("email") != target.email:
        issued = None
    access_form = CourseAccessForm(initial={"courses": [e.course_id for e in enrollments]})
    return render(
        request,
        "dashboard/user_detail.html",
        {"target": target, "items": items, "attempts": attempts, "issued": issued, "access_form": access_form},
    )


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


# ---------- А-5. Выдача учётных записей ----------
def _credentials_message(request, user, password, sent):
    if sent:
        messages.success(request, f"Логин и пароль отправлены на {user.email}.")
    else:
        messages.warning(request, "Письмо не отправилось — почта не настроена.")
    # пароль показываем один раз, чтобы администратор мог передать его вручную
    request.session["issued_credentials"] = {"email": user.email, "login": user.login, "password": password}


def set_course_access(user, courses):
    """Выдаёт доступ к выбранным курсам и забирает к остальным. Возвращает (добавлено, убрано)."""
    wanted = {c.pk for c in courses}
    current = set(user.enrollments.values_list("course_id", flat=True))
    added = wanted - current
    removed = current - wanted
    Enrollment.objects.bulk_create(Enrollment(user=user, course_id=pk) for pk in added)
    if removed:
        user.enrollments.filter(course_id__in=removed).delete()
    for course in Course.objects.filter(pk__in=added, is_published=True):
        Notification.objects.create(
            user=user, kind=Notification.Kind.NEW_COURSE, text=f"Вам открыт курс «{course.title}»", url=course.get_absolute_url()
        )
    return len(added), len(removed)


@staff_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        password = generate_password()
        with transaction.atomic():
            user = form.save(commit=False)
            if not user.login:
                user.login = generate_login(user.email)
            user.set_password(password)
            user.save()
            if not user.is_staff:
                set_course_access(user, form.cleaned_data["courses"])
        _credentials_message(request, user, password, send_credentials(request, user, password, is_new=True))
        return redirect("dashboard:user_detail", pk=user.pk)
    return render(request, "dashboard/user_form.html", {"form": form})


@staff_required
def user_edit(request, pk):
    """Изменение данных пользователя: имя, e-mail, логин, роль, активность, пароль."""
    target = get_object_or_404(User, pk=pk)
    protected = target.is_superuser and target != request.user
    form = UserEditForm(request.POST or None, instance=target)
    if protected:
        for name in ("new_password", "generate_password", "is_active", "is_staff"):
            form.fields[name].disabled = True
    if target == request.user:
        form.fields["is_active"].disabled = True
        form.fields["is_staff"].disabled = True
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        password = None
        if not protected:
            if form.cleaned_data.get("generate_password"):
                password = generate_password()
            elif form.cleaned_data.get("new_password"):
                password = form.cleaned_data["new_password"]
        if password:
            user.set_password(password)
        user.save()
        if password and form.cleaned_data.get("send_email"):
            _credentials_message(request, user, password, send_credentials(request, user, password, is_new=False))
        elif password:
            request.session["issued_credentials"] = {"email": user.email, "login": user.login, "password": password}
            messages.success(request, "Данные сохранены, пароль изменён.")
        else:
            messages.success(request, "Данные пользователя сохранены.")
        return redirect("dashboard:user_detail", pk=user.pk)
    return render(request, "dashboard/user_edit.html", {"form": form, "target": target})


@staff_required
def user_delete(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user or target.is_superuser:
        messages.error(request, "Нельзя удалить себя или суперпользователя.")
        return redirect("dashboard:user_detail", pk=pk)
    if request.method == "POST":
        name = target.full_name
        target.delete()
        messages.success(request, f"Пользователь {name} удалён вместе с его прогрессом.")
        return redirect("dashboard:user_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {"object": target, "kind": "пользователя", "back": "dashboard:user_detail", "back_pk": target.pk},
    )


@staff_required
@require_POST
def user_access(request, pk):
    """Выдача доступа к курсам, которые студент купил (оплаты на сайте нет)."""
    target = get_object_or_404(User, pk=pk)
    form = CourseAccessForm(request.POST)
    if form.is_valid():
        added, removed = set_course_access(target, form.cleaned_data["courses"])
        if added or removed:
            messages.success(request, f"Доступ обновлён: открыто курсов — {added}, закрыто — {removed}.")
        else:
            messages.info(request, "Доступ к курсам не изменился.")
    return redirect("dashboard:user_detail", pk=pk)


@staff_required
@require_POST
def user_reset_password(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.is_superuser and target != request.user:
        messages.error(request, "Пароль суперпользователя меняется только им самим.")
        return redirect("dashboard:user_detail", pk=pk)
    password = generate_password()
    target.set_password(password)
    target.save(update_fields=["password"])
    _credentials_message(request, target, password, send_credentials(request, target, password, is_new=False))
    return redirect("dashboard:user_detail", pk=pk)


# ---------- Материалы: общая библиотека видео и файлов для уроков ----------
@staff_required
def library(request):
    kind = request.GET.get("kind", "")
    items = LibraryItem.objects.annotate(
        video_total=Count("video_lessons", distinct=True), files_total=Count("material_lessons", distinct=True)
    )
    if kind in LibraryItem.Kind.values:
        items = items.filter(kind=kind)
    return render(
        request,
        "dashboard/library.html",
        {"items": items, "form": LibraryItemForm(), "kind": kind, "kinds": LibraryItem.Kind.choices},
    )


@staff_required
def library_form(request, pk=None):
    item = get_object_or_404(LibraryItem, pk=pk) if pk else None
    form = LibraryItemForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Материал «{obj.title}» сохранён.")
        return redirect("dashboard:library")
    lessons = []
    if item:
        lessons = list(item.video_lessons.select_related("level__course")) + list(
            item.material_lessons.select_related("level__course")
        )
    return render(request, "dashboard/library_form.html", {"form": form, "item": item, "lessons": lessons})


@staff_required
def library_delete(request, pk):
    item = get_object_or_404(LibraryItem, pk=pk)
    if request.method == "POST":
        title = item.title
        item.file.delete(save=False)
        item.delete()
        messages.success(request, f"Материал «{title}» удалён и отключён от уроков.")
        return redirect("dashboard:library")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {"object": item, "kind": "материал", "back": "dashboard:library_edit", "back_pk": item.pk},
    )
