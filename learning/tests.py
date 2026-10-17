"""Тесты правил обучения: регистрация, вход, открытие уровней, тесты, сертификат, админ-панель."""
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from courses.models import Course, Lesson, Level
from learning.models import Certificate, Enrollment, LessonProgress
from learning.services import build_course_state
from quizzes.models import Choice, Question, QuizAttempt

User = get_user_model()


def make_course(levels=2, lessons=2, questions=2, published=True):
    course = Course.objects.create(title="Тестовый курс", is_published=published)
    for li in range(1, levels + 1):
        level = Level.objects.create(course=course, title=f"Уровень {li}", order=li, pass_threshold=80)
        for i in range(1, lessons + 1):
            Lesson.objects.create(level=level, title=f"Урок {li}.{i}", order=i)
        for qi in range(1, questions + 1):
            q = Question.objects.create(level=level, text=f"Вопрос {qi}", order=qi)
            Choice.objects.create(question=q, text="Верно", is_correct=True)
            Choice.objects.create(question=q, text="Неверно", is_correct=False)
    return course


def answers(level, correct=True):
    data = {}
    for q in level.questions.all():
        data[f"q{q.pk}"] = q.choices.get(is_correct=correct).pk
    return data


class AccountsTests(TestCase):
    def test_no_self_registration(self):
        self.assertEqual(self.client.get("/accounts/register/").status_code, 404)
        self.assertNotContains(self.client.get(reverse("accounts:login")), "Зарегистрироваться")

    def test_admin_creates_user_and_credentials_are_emailed(self):
        admin = User.objects.create_user("adm@b.kg", "Strong-pass-42", full_name="Админ", is_staff=True)
        self.client.force_login(admin)
        r = self.client.post(reverse("dashboard:user_create"), {"full_name": "Нургуль  А.", "email": "N@Example.com"})
        user = User.objects.get(email="n@example.com")
        self.assertRedirects(r, reverse("dashboard:user_detail", args=[user.pk]), fetch_redirect_response=False)
        self.assertEqual(user.full_name, "Нургуль А.")
        self.assertFalse(user.is_staff)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("n@example.com", body)
        password = re.search(r"Пароль: (\S+)", body).group(1)
        self.assertTrue(user.check_password(password))
        self.assertNotEqual(user.password, password)  # в базе только хеш
        # пароль показан администратору один раз
        r = self.client.get(reverse("dashboard:user_detail", args=[user.pk]))
        self.assertContains(r, password)
        r = self.client.get(reverse("dashboard:user_detail", args=[user.pk]))
        self.assertNotContains(r, password)
        # новый пользователь входит с выданным паролем
        self.client.logout()
        r = self.client.post(reverse("accounts:login"), {"username": "n@example.com", "password": password})
        self.assertRedirects(r, reverse("learning:my_courses"), fetch_redirect_response=False)

    def test_admin_cannot_create_duplicate_email(self):
        admin = User.objects.create_user("adm@b.kg", "Strong-pass-42", full_name="Админ", is_staff=True)
        User.objects.create_user("a@b.kg", "Strong-pass-42", full_name="A")
        self.client.force_login(admin)
        r = self.client.post(reverse("dashboard:user_create"), {"full_name": "B", "email": "A@b.kg"})
        self.assertContains(r, "уже есть")

    def test_admin_reissues_password(self):
        admin = User.objects.create_user("adm@b.kg", "Strong-pass-42", full_name="Админ", is_staff=True)
        user = User.objects.create_user("u@b.kg", "Old-pass-42", full_name="U")
        self.client.force_login(admin)
        self.client.post(reverse("dashboard:user_reset_password", args=[user.pk]))
        user.refresh_from_db()
        self.assertFalse(user.check_password("Old-pass-42"))
        password = re.search(r"Пароль: (\S+)", mail.outbox[0].body).group(1)
        self.assertTrue(user.check_password(password))

    def test_regular_user_cannot_create_users(self):
        user = User.objects.create_user("u@b.kg", "Strong-pass-42", full_name="U")
        self.client.force_login(user)
        r = self.client.post(reverse("dashboard:user_create"), {"full_name": "X", "email": "x@b.kg"})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(User.objects.filter(email="x@b.kg").exists())

    def test_blocked_user_cannot_login(self):
        User.objects.create_user("b@b.kg", "Strong-pass-42", full_name="B", is_active=False)
        r = self.client.post(reverse("accounts:login"), {"username": "b@b.kg", "password": "Strong-pass-42"})
        self.assertContains(r, "заблокирован")

    def test_password_reset_sends_link(self):
        User.objects.create_user("c@b.kg", "Strong-pass-42", full_name="C")
        self.client.post(reverse("accounts:password_reset"), {"email": "c@b.kg"})
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"http://testserver(\S+)", mail.outbox[0].body).group(1)
        r = self.client.get(link, follow=True)
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "New-strong-77", "new_password2": "New-strong-77"})
        self.assertRedirects(r, reverse("accounts:password_reset_complete"))
        self.assertTrue(User.objects.get(email="c@b.kg").check_password("New-strong-77"))


class LearningFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("s@b.kg", "Strong-pass-42", full_name="Студент")
        self.client.force_login(self.user)
        self.course = make_course()
        self.level1, self.level2 = self.course.levels.all()

    def enroll(self):
        self.client.post(reverse("courses:enroll", args=[self.course.pk]))

    def watch_level(self, level):
        for lesson in level.lessons.all():
            r = self.client.post(reverse("courses:lesson_watched", args=[lesson.pk]), HTTP_X_REQUESTED_WITH="fetch")
            self.assertEqual(r.status_code, 200)

    def test_catalog_hides_unpublished(self):
        hidden = make_course(published=False)
        hidden.title = "Скрытый"
        hidden.save()
        r = self.client.get(reverse("courses:catalog"))
        self.assertNotContains(r, "Скрытый")

    def test_catalog_search_cyrillic_case_insensitive(self):
        r = self.client.get(reverse("courses:catalog"), {"q": "ТЕСТОВЫЙ"})
        self.assertContains(r, "Тестовый курс")

    def test_lesson_requires_enrollment(self):
        lesson = self.level1.lessons.first()
        r = self.client.get(reverse("courses:lesson", args=[lesson.pk]))
        self.assertRedirects(r, self.course.get_absolute_url())

    def test_second_level_locked_until_quiz_passed(self):
        self.enroll()
        locked = self.level2.lessons.first()
        r = self.client.post(reverse("courses:lesson_watched", args=[locked.pk]), HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.status_code, 403)
        self.watch_level(self.level1)
        self.client.post(reverse("quizzes:take", args=[self.level1.pk]), answers(self.level1, correct=True))
        r = self.client.get(reverse("courses:lesson", args=[locked.pk]))
        self.assertEqual(r.status_code, 200)

    def test_quiz_closed_until_lessons_watched(self):
        self.enroll()
        r = self.client.get(reverse("quizzes:take", args=[self.level1.pk]))
        self.assertRedirects(r, self.course.get_absolute_url())

    def test_quiz_page_does_not_leak_correct_answers(self):
        self.enroll()
        self.watch_level(self.level1)
        r = self.client.get(reverse("quizzes:take", args=[self.level1.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "is_correct")

    def test_failed_quiz_keeps_level_locked_and_allows_retry(self):
        self.enroll()
        self.watch_level(self.level1)
        r = self.client.post(reverse("quizzes:take", args=[self.level1.pk]), answers(self.level1, correct=False))
        attempt = QuizAttempt.objects.get()
        self.assertRedirects(r, reverse("quizzes:result", args=[attempt.pk]))
        self.assertFalse(attempt.passed)
        self.assertEqual(attempt.score, 0)
        state = build_course_state(self.user, self.course)
        self.assertFalse(state.levels[1].unlocked)
        r = self.client.get(reverse("quizzes:take", args=[self.level1.pk]))
        self.assertEqual(r.status_code, 200)

    def test_threshold_is_respected(self):
        self.level1.pass_threshold = 100
        self.level1.save()
        self.enroll()
        self.watch_level(self.level1)
        data = answers(self.level1, correct=True)
        first_q = self.level1.questions.first()
        data[f"q{first_q.pk}"] = first_q.choices.get(is_correct=False).pk
        self.client.post(reverse("quizzes:take", args=[self.level1.pk]), data)
        attempt = QuizAttempt.objects.get()
        self.assertEqual(attempt.score, 50)
        self.assertFalse(attempt.passed)

    def test_full_course_gives_certificate_and_100_percent(self):
        self.enroll()
        for level in (self.level1, self.level2):
            self.watch_level(level)
            self.client.post(reverse("quizzes:take", args=[level.pk]), answers(level, correct=True))
        enrollment = Enrollment.objects.get(user=self.user, course=self.course)
        self.assertTrue(enrollment.is_completed)
        cert = Certificate.objects.get(enrollment=enrollment)
        self.assertEqual(build_course_state(self.user, self.course).percent, 100)
        r = self.client.get(reverse("learning:certificate", args=[cert.number]))
        self.assertContains(r, "Студент")

    def test_level_without_quiz_completes_after_lessons(self):
        course = make_course(levels=2, lessons=1, questions=0)
        self.client.post(reverse("courses:enroll", args=[course.pk]))
        first, second = course.levels.all()
        self.watch_level(first)
        self.assertTrue(build_course_state(self.user, course).levels[1].unlocked)

    def test_progress_page(self):
        self.enroll()
        self.watch_level(self.level1)
        r = self.client.get(reverse("learning:progress"))
        self.assertContains(r, "Тестовый курс")
        self.assertEqual(LessonProgress.objects.filter(user=self.user).count(), 2)


class DashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm@b.kg", "Strong-pass-42", full_name="Админ", is_staff=True)
        self.user = User.objects.create_user("u@b.kg", "Strong-pass-42", full_name="Юзер")

    def test_dashboard_forbidden_for_users(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("dashboard:index")).status_code, 403)

    def test_admin_creates_course_level_question(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("dashboard:course_create"), {"title": "Новый", "description": "x", "difficulty": "beginner"})
        course = Course.objects.get(title="Новый")
        self.assertRedirects(r, reverse("dashboard:course_edit", args=[course.pk]))
        self.client.post(reverse("dashboard:level_create", args=[course.pk]), {"title": "L1", "order": 1, "pass_threshold": 70})
        level = course.levels.get()
        data = {
            "text": "2+2?", "order": 1,
            "choices-TOTAL_FORMS": 4, "choices-INITIAL_FORMS": 0, "choices-MIN_NUM_FORMS": 0, "choices-MAX_NUM_FORMS": 8,
            "choices-0-text": "4", "choices-0-is_correct": "on",
            "choices-1-text": "5",
        }
        self.client.post(reverse("dashboard:question_create", args=[level.pk]), data)
        q = level.questions.get()
        self.assertEqual(q.choices.count(), 2)

    def test_question_needs_exactly_one_correct(self):
        self.client.force_login(self.admin)
        course = make_course(levels=1, questions=0)
        level = course.levels.get()
        data = {
            "text": "?", "order": 1,
            "choices-TOTAL_FORMS": 2, "choices-INITIAL_FORMS": 0, "choices-MIN_NUM_FORMS": 0, "choices-MAX_NUM_FORMS": 8,
            "choices-0-text": "a", "choices-1-text": "b",
        }
        r = self.client.post(reverse("dashboard:question_create", args=[level.pk]), data)
        self.assertContains(r, "ровно один правильный")

    def test_block_user(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:user_block", args=[self.user.pk]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_lesson_rejects_bad_video_type(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.admin)
        level = make_course(levels=1, lessons=0, questions=0).levels.get()
        data = {
            "title": "Видео", "order": 1, "description": "",
            "video_file": SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream"),
            "materials-TOTAL_FORMS": 0, "materials-INITIAL_FORMS": 0, "materials-MIN_NUM_FORMS": 0, "materials-MAX_NUM_FORMS": 1000,
        }
        r = self.client.post(reverse("dashboard:lesson_create", args=[level.pk]), data)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Lesson.objects.filter(title="Видео").exists())
