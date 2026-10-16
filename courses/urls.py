from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("courses/<int:pk>/", views.course_detail, name="detail"),
    path("courses/<int:pk>/enroll/", views.enroll, name="enroll"),
    path("lessons/<int:pk>/", views.lesson_detail, name="lesson"),
    path("lessons/<int:pk>/watched/", views.lesson_watched, name="lesson_watched"),
    path("materials/<int:pk>/download/", views.material_download, name="material_download"),
]
