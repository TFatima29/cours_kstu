from django.contrib import admin

from .models import Course, Lesson, Level, Material


class LevelInline(admin.TabularInline):
    model = Level
    extra = 0


class MaterialInline(admin.TabularInline):
    model = Material
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title", "is_published", "created_at"]
    list_filter = ["is_published"]
    search_fields = ["title"]
    inlines = [LevelInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["title", "level", "order"]
    list_filter = ["level__course"]
    inlines = [MaterialInline]


admin.site.register(Level)
