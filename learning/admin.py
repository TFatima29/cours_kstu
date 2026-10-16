from django.contrib import admin

from .models import Certificate, Enrollment, LessonProgress


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["user", "course", "enrolled_at", "completed_at"]


admin.site.register(LessonProgress)
admin.site.register(Certificate)
