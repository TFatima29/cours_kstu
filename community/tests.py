from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from community.models import Comment, Notification
from courses.models import Category, Course
from learning.models import Certificate, Enrollment
from learning.tests import answers, make_course

User = get_user_model()


class CommunityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("s@b.kg", "Strong-pass-42", full_name="Студент Один")
        self.other = User.objects.create_user("o@b.kg", "Strong-pass-42", full_name="Студент Два")
        self.course = make_course(levels=2, lessons=1, questions=1)
        self.level1, self.level2 = self.course.levels.all()
        self.lesson = self.level1.lessons.first()

    def enroll(self, user):
        self.client.force_login(user)
        Enrollment.objects.get_or_create(user=user, course=self.course)

    def test_comment_requires_enrollment(self):
        self.client.force_login(self.user)
        self.client.post(reverse("community:add_comment", args=[self.lesson.pk]), {"text": "Привет"})
        self.assertFalse(Comment.objects.exists())

    def test_reply_notifies_author(self):
        self.enroll(self.user)
        self.client.post(reverse("community:add_comment", args=[self.lesson.pk]), {"text": "Вопрос"})
        parent = Comment.objects.get()
        self.enroll(self.other)
        self.client.post(reverse("community:add_comment", args=[self.lesson.pk]), {"text": "Ответ", "parent": parent.pk})
        self.assertEqual(Notification.objects.filter(user=self.user, kind="reply").count(), 1)
        r = self.client.get(self.lesson.get_absolute_url())
        self.assertContains(r, "Ответ")

    def test_level_unlock_and_completion_notifications(self):
        self.enroll(self.user)
        for level in (self.level1, self.level2):
            for lesson in level.lessons.all():
                self.client.post(reverse("courses:lesson_watched", args=[lesson.pk]), HTTP_X_REQUESTED_WITH="fetch")
            self.client.post(reverse("quizzes:take", args=[level.pk]), answers(level))
        kinds = list(Notification.objects.filter(user=self.user).values_list("kind", flat=True))
        self.assertIn("level", kinds)
        self.assertIn("course", kinds)
        r = self.client.get(reverse("community:notifications"))
        self.assertContains(r, "пройден")
        self.assertFalse(Notification.objects.filter(user=self.user, is_read=False).exists())

    def test_verify_certificate_short_number(self):
        self.enroll(self.user)
        for level in (self.level1, self.level2):
            for lesson in level.lessons.all():
                self.client.post(reverse("courses:lesson_watched", args=[lesson.pk]), HTTP_X_REQUESTED_WITH="fetch")
            self.client.post(reverse("quizzes:take", args=[level.pk]), answers(level))
        cert = Certificate.objects.get()
        r = self.client.get(reverse("learning:verify"), {"number": cert.short_number})
        self.assertContains(r, "действителен")
        r = self.client.get(reverse("learning:verify"), {"number": "00000000"})
        self.assertContains(r, "не найден")

    def test_catalog_filters_by_category_and_level(self):
        cat = Category.objects.create(name="Дизайн")
        Course.objects.create(title="Фигма", is_published=True, category=cat, difficulty="advanced")
        r = self.client.get(reverse("courses:catalog"), {"category": cat.pk})
        self.assertContains(r, "Фигма")
        self.assertNotContains(r, "Тестовый курс")
        r = self.client.get(reverse("courses:catalog"), {"level": "beginner"})
        self.assertNotContains(r, "Фигма</h3>")

    def test_publish_announces_course_once(self):
        admin = User.objects.create_user("a@b.kg", "Strong-pass-42", full_name="Админ", is_staff=True)
        hidden = Course.objects.create(title="Новинка", is_published=False)
        self.client.force_login(admin)
        self.client.post(reverse("dashboard:course_publish", args=[hidden.pk]))
        self.client.post(reverse("dashboard:course_publish", args=[hidden.pk]))
        self.client.post(reverse("dashboard:course_publish", args=[hidden.pk]))
        self.assertEqual(Notification.objects.filter(kind="new_course").count(), 2)  # два обучающихся, по одному разу

    def test_theme_switch(self):
        for theme in ("ice", "track", "studio", "route"):
            self.client.post(reverse("community:set_theme"), {"theme": theme, "next": "/"})
            r = self.client.get(reverse("courses:catalog"))
            self.assertContains(r, f'data-variant="{theme}"')
        r = self.client.post(reverse("community:set_theme"), {"theme": "ice", "next": "https://evil.example/"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
