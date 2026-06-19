from django.contrib import admin, messages
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .decorators import rm_login_required
from .forms import ChangePasswordForm, LoginForm
from .models import RMUser
from .utils import get_authenticated_rm


@require_http_methods(["GET", "POST"])
def login_view(request):
    if get_authenticated_rm(request):
        return redirect("rm_auth:dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user_id = form.cleaned_data["user_id"].strip()
        password = form.cleaned_data["password"]

        try:
            rm_user = RMUser.objects.get(user_id__iexact=user_id, is_active=True)
        except RMUser.DoesNotExist:
            rm_user = None

        if rm_user and rm_user.check_password(password):
            request.session[settings.RM_SESSION_KEY] = rm_user.pk
            request.session.cycle_key()
            messages.success(request, f"Welcome back, {rm_user.user_id}.")
            return redirect("rm_auth:dashboard")

        messages.error(request, "Invalid User ID or password.")

    return render(request, "rm_auth/login.html", {"form": form})


@require_POST
def logout_view(request):
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect("rm_auth:login")


@rm_login_required
@require_http_methods(["GET", "POST"])
def change_password_view(request):
    rm_user = get_authenticated_rm(request)
    initial = {"user_id": rm_user.user_id, "email": rm_user.email}
    form = ChangePasswordForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        user_id = form.cleaned_data["user_id"].strip()
        old_password = form.cleaned_data["old_password"]
        email = form.cleaned_data["email"].strip().lower()
        new_password = form.cleaned_data["new_password"]

        if user_id.lower() != rm_user.user_id.lower():
            messages.error(request, "User ID does not match your account.")
        elif not rm_user.check_password(old_password):
            messages.error(request, "Current password is incorrect.")
        elif email != rm_user.email.lower():
            messages.error(request, "Email does not match the registered address.")
        else:
            rm_user.set_password(new_password)
            rm_user.save(update_fields=["password"])
            send_mail(
                subject="CRM Bank — Password updated",
                message=(
                    f"Hello {rm_user.user_id},\n\n"
                    "Your Relationship Manager account password was changed successfully.\n\n"
                    "If you did not make this change, contact your administrator immediately."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[rm_user.email],
                fail_silently=False,
            )
            messages.success(request, "Password updated. A confirmation email has been sent.")
            return redirect("rm_auth:dashboard")

    return render(
        request,
        "rm_auth/change_password.html",
        {"form": form, "rm_user": rm_user},
    )


@rm_login_required
def dashboard_view(request):
    rm_user = get_authenticated_rm(request)
    return render(request, "rm_auth/dashboard.html", {"rm_user": rm_user})
