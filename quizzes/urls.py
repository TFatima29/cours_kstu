from django.urls import path

from . import views

app_name = "quizzes"

urlpatterns = [
    path("levels/<int:level_id>/quiz/", views.take_quiz, name="take"),
    path("quiz/result/<int:attempt_id>/", views.quiz_result, name="result"),
]
