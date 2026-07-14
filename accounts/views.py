from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import TeacherRegistrationForm


def register_view(request):
    """Registra una nueva cuenta de docente."""

    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = TeacherRegistrationForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Tu cuenta fue creada correctamente. Ya puedes iniciar sesión.",
            )

            return redirect("accounts:login")
    else:
        form = TeacherRegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )


def login_view(request):
    """Inicia la sesión del docente."""

    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)

            messages.success(
                request,
                f"Bienvenido, {user.first_name or user.username}.",
            )

            return redirect("accounts:dashboard")

        messages.error(
            request,
            "El usuario o la contraseña son incorrectos.",
        )

    return render(request, "accounts/login.html")


@login_required
def dashboard_view(request):
    """Muestra el panel principal del docente."""

    return render(request, "accounts/dashboard.html")


def logout_view(request):
    """Cierra la sesión del usuario."""

    if request.method == "POST":
        logout(request)

        messages.success(
            request,
            "La sesión se cerró correctamente.",
        )

    return redirect("core:home")