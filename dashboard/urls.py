from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("courses/", views.course_list, name="course_list"),
    path("courses/new/", views.course_create, name="course_create"),
    path("courses/<int:pk>/", views.course_edit, name="course_edit"),
    path("courses/<int:pk>/publish/", views.course_toggle_publish, name="course_publish"),
    path("courses/<int:pk>/delete/", views.course_delete, name="course_delete"),
    path("courses/<int:course_pk>/levels/new/", views.level_create, name="level_create"),
    path("levels/<int:pk>/", views.level_edit, name="level_edit"),
    path("levels/<int:pk>/delete/", views.level_delete, name="level_delete"),
    path("levels/<int:level_pk>/lessons/new/", views.lesson_form, name="lesson_create"),
    path("lessons/<int:pk>/", views.lesson_form, name="lesson_edit"),
    path("lessons/<int:pk>/delete/", views.lesson_delete, name="lesson_delete"),
    path("levels/<int:level_pk>/questions/new/", views.question_form, name="question_create"),
    path("questions/<int:pk>/", views.question_form, name="question_edit"),
    path("questions/<int:pk>/delete/", views.question_delete, name="question_delete"),
    path("categories/", views.categories, name="categories"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/block/", views.user_toggle_block, name="user_block"),
]
