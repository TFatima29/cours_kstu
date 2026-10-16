from django.contrib import admin

from .models import Choice, Question, QuizAttempt


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "level", "order"]
    list_filter = ["level__course"]
    inlines = [ChoiceInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "level", "score", "passed", "created_at"]
    list_filter = ["passed"]
