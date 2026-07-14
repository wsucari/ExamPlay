from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import QuizForm
from .models import Quiz


@login_required
def quiz_list(request):
    """Lista los cuestionarios pertenecientes al docente."""

    quizzes = (
        Quiz.objects
        .filter(teacher=request.user)
        .prefetch_related("questions")
    )

    return render(
        request,
        "quizzes/quiz_list.html",
        {
            "quizzes": quizzes,
        },
    )


@login_required
def quiz_create(request):
    """Crea un nuevo cuestionario."""

    if request.method == "POST":
        form = QuizForm(request.POST)

        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.teacher = request.user
            quiz.save()

            messages.success(
                request,
                "El cuestionario fue creado correctamente.",
            )

            return redirect(
                "quizzes:detail",
                pk=quiz.pk,
            )
    else:
        form = QuizForm()

    return render(
        request,
        "quizzes/quiz_form.html",
        {
            "form": form,
            "page_title": "Crear cuestionario",
            "button_text": "Crear cuestionario",
        },
    )


@login_required
def quiz_detail(request, pk):
    """Muestra un cuestionario y sus preguntas."""

    quiz = get_object_or_404(
        Quiz.objects.prefetch_related("questions__options"),
        pk=pk,
        teacher=request.user,
    )

    return render(
        request,
        "quizzes/quiz_detail.html",
        {
            "quiz": quiz,
        },
    )


@login_required
def quiz_update(request, pk):
    """Edita un cuestionario del docente."""

    quiz = get_object_or_404(
        Quiz,
        pk=pk,
        teacher=request.user,
    )

    if request.method == "POST":
        form = QuizForm(
            request.POST,
            instance=quiz,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "El cuestionario fue actualizado correctamente.",
            )

            return redirect(
                "quizzes:detail",
                pk=quiz.pk,
            )
    else:
        form = QuizForm(instance=quiz)

    return render(
        request,
        "quizzes/quiz_form.html",
        {
            "form": form,
            "quiz": quiz,
            "page_title": "Editar cuestionario",
            "button_text": "Guardar cambios",
        },
    )


@login_required
def quiz_delete(request, pk):
    """Elimina un cuestionario del docente."""

    quiz = get_object_or_404(
        Quiz,
        pk=pk,
        teacher=request.user,
    )

    if request.method == "POST":
        title = quiz.title
        quiz.delete()

        messages.success(
            request,
            f'El cuestionario "{title}" fue eliminado.',
        )

        return redirect("quizzes:list")

    return render(
        request,
        "quizzes/quiz_confirm_delete.html",
        {
            "quiz": quiz,
        },
    )