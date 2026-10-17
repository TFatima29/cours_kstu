from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import RegisterForm
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = RegisterForm
    ordering = ["-date_joined"]
    list_display = ["email", "login", "full_name", "is_staff", "is_active", "date_joined"]
    search_fields = ["email", "login", "full_name"]
    fieldsets = (
        (None, {"fields": ("email", "login", "password")}),
        ("Личные данные", {"fields": ("full_name", "avatar")}),
        ("Права", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),)
