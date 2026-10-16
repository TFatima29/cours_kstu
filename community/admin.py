from django.contrib import admin

from .models import Comment, Notification


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["user", "lesson", "created_at", "is_hidden"]
    list_filter = ["is_hidden"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "text", "is_read", "created_at"]
