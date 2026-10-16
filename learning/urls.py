from django.urls import path

from . import views

app_name = "learning"

urlpatterns = [
    path("my/", views.my_courses, name="my_courses"),
    path("my/progress/", views.my_progress, name="progress"),
    path("certificates/verify/", views.verify_certificate, name="verify"),
    path("certificates/<uuid:number>/", views.certificate, name="certificate"),
]
