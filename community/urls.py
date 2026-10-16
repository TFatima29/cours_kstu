from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("lessons/<int:lesson_pk>/comments/", views.add_comment, name="add_comment"),
    path("comments/<int:pk>/delete/", views.delete_comment, name="delete_comment"),
    path("theme/", views.set_theme, name="set_theme"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/<int:pk>/", views.open_notification, name="open_notification"),
]
