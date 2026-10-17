from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import LoginForm, ProfileForm


class LoginView(auth_views.LoginView):
    """Ф-2. Вход."""

    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        # после входа каждая роль попадает на свою стартовую страницу
        from django.urls import reverse

        from .roles import home_url_name

        return reverse(home_url_name(self.request.user))


class LogoutView(auth_views.LogoutView):
    """Ф-2. Выход (только POST-запросом)."""


@login_required
def profile(request):
    """Ф-13. Профиль: имя, аватар."""
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST":
        if request.POST.get("remove_avatar") and request.user.avatar:
            request.user.avatar.delete(save=True)
            messages.success(request, "Аватар удалён.")
            return redirect("accounts:profile")
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль сохранён.")
            return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


class PasswordChangeView(auth_views.PasswordChangeView):
    """Ф-13. Смена пароля."""

    form_class = PasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, "Пароль изменён.")
        return super().form_valid(form)


# Ф-3. Восстановление пароля по ссылке из письма
class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/email/password_reset_email.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
