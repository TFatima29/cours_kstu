"""Демо-данные: администратор, обучающийся и два курса с уровнями, уроками и тестами.

Запуск: python manage.py seed_demo
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Category, Course, Lesson, Level, Material
from learning.models import Enrollment
from quizzes.models import Choice, Question

DEMO_DIR = Path(settings.BASE_DIR) / "demo"

COURSES = [
    {
        "title": "Python с нуля",
        "category": "Программирование",
        "difficulty": "beginner",
        "short": "Переменные, условия, циклы и функции — на коротких видео и простых задачах.",
        "description": (
            "Курс для тех, кто никогда не программировал. Каждый уровень — одна большая тема: "
            "сначала смотрите короткие уроки, потом проверяете себя тестом.\n\n"
            "После курса вы сможете написать небольшую программу: калькулятор, угадайку или список дел."
        ),
        "levels": [
            {
                "title": "Первые шаги",
                "lessons": ["Установка Python и первая программа", "Переменные и типы данных"],
                "questions": [
                    ("Какая функция выводит текст на экран?", ["print()", "input()", "len()", "type()"], 0),
                    ("Какой тип у значения 3.14?", ["int", "str", "float", "bool"], 2),
                    ("Как правильно создать переменную?", ["5 = x", "x = 5", "var x 5", "x := 5 :"], 1),
                ],
            },
            {
                "title": "Условия и циклы",
                "lessons": ["Условия if / elif / else", "Цикл for и range()", "Цикл while"],
                "questions": [
                    ("Сколько раз выполнится for i in range(3)?", ["2", "3", "4", "Бесконечно"], 1),
                    ("Какой оператор проверяет равенство?", ["=", "==", "===", "!="], 1),
                    ("Что прерывает цикл?", ["stop", "exit", "break", "pass"], 2),
                ],
            },
            {
                "title": "Функции",
                "lessons": ["Объявление функций", "Аргументы и return"],
                "questions": [
                    ("Каким словом объявляют функцию?", ["func", "def", "function", "lambda"], 1),
                    ("Что вернёт функция без return?", ["0", "''", "None", "Ошибку"], 2),
                ],
            },
        ],
    },
    {
        "title": "Вёрстка: HTML и CSS",
        "category": "Веб-разработка",
        "difficulty": "beginner",
        "short": "Как устроена веб-страница: теги, стили, отступы и адаптивная сетка.",
        "description": "Соберёте свою первую страницу и научитесь делать её удобной на телефоне.",
        "levels": [
            {
                "title": "Основы HTML",
                "lessons": ["Структура документа", "Заголовки, абзацы и ссылки"],
                "questions": [
                    ("Какой тег создаёт ссылку?", ["<link>", "<a>", "<href>", "<url>"], 1),
                    ("Где пишут видимое содержимое страницы?", ["<head>", "<body>", "<meta>", "<title>"], 1),
                ],
            },
            {
                "title": "Стили CSS",
                "lessons": ["Селекторы и свойства", "Flexbox"],
                "questions": [
                    ("Какое свойство меняет цвет текста?", ["background", "font", "color", "text-color"], 2),
                    ("Что включает flex-раскладку?", ["display: flex", "flex: on", "layout: flex", "position: flex"], 0),
                ],
            },
        ],
    },
    {
        "title": "SQL и базы данных",
        "category": "Программирование",
        "difficulty": "intermediate",
        "short": "SELECT, JOIN, группировки и проектирование таблиц на примере базы студентов.",
        "description": "Для тех, кто знает основы программирования и хочет уверенно работать с данными.",
        "levels": [
            {
                "title": "Запросы SELECT",
                "lessons": ["Выборка и фильтрация", "Сортировка и LIMIT"],
                "questions": [
                    ("Какой оператор фильтрует строки?", ["ORDER BY", "WHERE", "GROUP BY", "FROM"], 1),
                    ("Как выбрать все столбцы?", ["SELECT ALL", "SELECT *", "SELECT columns", "GET *"], 1),
                ],
            },
            {
                "title": "Соединения таблиц",
                "lessons": ["INNER JOIN", "LEFT JOIN"],
                "questions": [
                    ("Какой JOIN сохраняет все строки левой таблицы?", ["INNER", "LEFT", "CROSS", "SELF"], 1),
                ],
            },
        ],
    },
    {
        "title": "UX/UI-дизайн: основы",
        "category": "Дизайн",
        "difficulty": "beginner",
        "short": "Как исследовать пользователей, рисовать макеты и проверять их на людях.",
        "description": "Разберёте путь от идеи до кликабельного прототипа и научитесь замечать ошибки интерфейса.",
        "levels": [
            {
                "title": "Исследование",
                "lessons": ["Кто ваш пользователь", "Интервью и сценарии"],
                "questions": [
                    ("Что такое персона?", ["Шрифт", "Портрет типичного пользователя", "Цветовая схема", "Логотип"], 1),
                ],
            },
        ],
    },
    {
        "title": "Английский для IT",
        "category": "Языки",
        "difficulty": "intermediate",
        "short": "Читать документацию, писать коммиты и проходить собеседования на английском.",
        "description": "Лексика разработчика, грамматика технических текстов и практика устной речи.",
        "levels": [
            {
                "title": "Документация",
                "lessons": ["Как читать README", "Термины в коде"],
                "questions": [
                    ("Что значит deprecated?", ["Новый", "Устаревший", "Быстрый", "Скрытый"], 1),
                ],
            },
        ],
    },
    {
        "title": "JavaScript для веба",
        "category": "Веб-разработка",
        "difficulty": "advanced",
        "short": "DOM, события, fetch и асинхронность — делаем страницы живыми.",
        "description": "Курс для тех, кто уже сверстал пару страниц и хочет добавить в них логику.",
        "levels": [
            {
                "title": "DOM и события",
                "lessons": ["Поиск элементов", "Обработчики событий"],
                "questions": [
                    ("Какой метод находит элемент по селектору?", ["getElement()", "querySelector()", "find()", "select()"], 1),
                ],
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Создаёт демонстрационных пользователей и курсы"

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        admin, created = User.objects.get_or_create(
            email="admin@courseplatform.local",
            defaults={"full_name": "Администратор платформы", "login": "admin", "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password("admin12345")
            admin.save()
        student, created = User.objects.get_or_create(
            email="student@courseplatform.local", defaults={"full_name": "Айгерим Садыкова", "login": "student"}
        )
        if created:
            student.set_password("student12345")
            student.save()

        video = DEMO_DIR / "demo_lesson.mp4"
        pdf = DEMO_DIR / "konspekt.pdf"
        for index, spec in enumerate(COURSES):
            if Course.objects.filter(title=spec["title"]).exists():
                continue
            category, _ = Category.objects.get_or_create(name=spec["category"])
            course = Course.objects.create(
                title=spec["title"],
                category=category,
                difficulty=spec["difficulty"],
                short_description=spec["short"],
                description=spec["description"],
                price=index * 1500,
                is_published=True,
            )
            if index < 2:  # доступ выдаёт администратор: демо-студенту открыты первые два курса
                Enrollment.objects.get_or_create(user=student, course=course)
            for li, lv in enumerate(spec["levels"], start=1):
                level = Level.objects.create(course=course, title=lv["title"], order=li)
                for i, title in enumerate(lv["lessons"], start=1):
                    lesson = Lesson.objects.create(
                        level=level,
                        title=title,
                        order=i,
                        description=f"Короткий видеоурок по теме «{title}». Посмотрите видео до конца и откройте конспект.",
                    )
                    if video.exists():
                        with video.open("rb") as fh:
                            lesson.video_file.save(f"lesson_{lesson.pk}.mp4", File(fh), save=True)
                    if pdf.exists() and i == 1:
                        with pdf.open("rb") as fh:
                            m = Material(lesson=lesson, title="Конспект урока")
                            m.file.save(f"konspekt_{lesson.pk}.pdf", File(fh), save=True)
                for qi, (text, options, right) in enumerate(lv["questions"], start=1):
                    q = Question.objects.create(level=level, text=text, order=qi)
                    for oi, opt in enumerate(options):
                        Choice.objects.create(question=q, text=opt, is_correct=(oi == right))
            self.stdout.write(self.style.SUCCESS(f"Курс «{course.title}» создан"))

        self.stdout.write(self.style.SUCCESS("Готово."))
        self.stdout.write("Администратор: admin (или admin@courseplatform.local) / admin12345")
        self.stdout.write("Обучающийся:   student (или student@courseplatform.local) / student12345")
