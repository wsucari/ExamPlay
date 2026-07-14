from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from livegames.models import GameSession
from quizzes.models import Quiz

from .forms import TeacherRegistrationForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = TeacherRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tu cuenta fue creada correctamente. Ya puedes iniciar sesión.")
        return redirect("accounts:login")
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        user = authenticate(request, username=username, password=request.POST.get("password", ""))
        if user is not None:
            login(request, user)
            messages.success(request, f"Bienvenido, {user.first_name or user.username}.")
            next_url = request.POST.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect("accounts:dashboard")
        messages.error(request, "El usuario o la contraseña son incorrectos.")
    return render(request, "accounts/login.html", {"next": request.GET.get("next", "")})


@login_required
def dashboard_view(request):
    hosted = GameSession.objects.filter(host=request.user)
    stats = {
        "quiz_count": Quiz.objects.filter(teacher=request.user).count(),
        "game_count": hosted.count(),
        "participant_count": hosted.aggregate(total=Count("participants"))["total"] or 0,
    }
    return render(request, "accounts/dashboard.html", {"stats": stats})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "La sesión se cerró correctamente.")
    return redirect("core:home")
