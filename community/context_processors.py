from django.conf import settings

THEMES = {
    "route": "Маршрут",
    "ice": "Лёд",
    "track": "Трасса",
    "studio": "Студия",
}


def site(request):
    """Счётчик непрочитанных уведомлений и текущий вариант оформления."""
    unread = 0
    if request.user.is_authenticated:
        unread = request.user.notifications.filter(is_read=False).count()
    theme = request.session.get("site_theme") or getattr(settings, "SITE_THEME", "route")
    if theme not in THEMES:
        theme = "route"
    return {"unread_notifications": unread, "site_theme": theme, "site_themes": THEMES}
