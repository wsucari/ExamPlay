from django.shortcuts import render


def home(request):
    """Muestra la página principal de ExamPlay."""
    return render(request, "core/home.html")