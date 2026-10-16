from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Course Platform — администрирование"
admin.site.site_title = "Course Platform"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("manage/", include("dashboard.urls")),
    path("", include("community.urls")),
    path("", include("learning.urls")),
    path("", include("quizzes.urls")),
    path("", include("courses.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
