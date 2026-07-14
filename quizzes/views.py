from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Count, Max
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AnswerOptionFormSet, QuestionForm, QuizForm
from .models import Question, Quiz


def owned_quiz(user, pk):
    return get_object_or_404(Quiz, pk=pk, teacher=user)


@login_required
def quiz_list(request):
    quizzes = Quiz.objects.filter(teacher=request.user).annotate(question_total=Count("questions"))
    return render(request, "quizzes/quiz_list.html", {"quizzes": quizzes})


@login_required
def quiz_create(request):
    form = QuizForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        quiz = form.save(commit=False)
        quiz.teacher = request.user
        quiz.save()
        messages.success(request, "El cuestionario fue creado correctamente.")
        return redirect("quizzes:detail", pk=quiz.pk)
    return render(request, "quizzes/quiz_form.html", {"form": form, "page_title": "Crear cuestionario", "button_text": "Crear cuestionario"})


@login_required
def quiz_detail(request, pk):
    quiz = get_object_or_404(Quiz.objects.prefetch_related("questions__options"), pk=pk, teacher=request.user)
    return render(request, "quizzes/quiz_detail.html", {"quiz": quiz})


@login_required
def quiz_update(request, pk):
    quiz = owned_quiz(request.user, pk)
    form = QuizForm(request.POST or None, instance=quiz)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "El cuestionario fue actualizado correctamente.")
        return redirect("quizzes:detail", pk=quiz.pk)
    return render(request, "quizzes/quiz_form.html", {"form": form, "quiz": quiz, "page_title": "Editar cuestionario", "button_text": "Guardar cambios"})


@login_required
def quiz_delete(request, pk):
    quiz = owned_quiz(request.user, pk)
    if request.method == "POST":
        title = quiz.title
        quiz.delete()
        messages.success(request, f'El cuestionario "{title}" fue eliminado.')
        return redirect("quizzes:list")
    return render(request, "quizzes/quiz_confirm_delete.html", {"quiz": quiz})


@login_required
def quiz_toggle(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    quiz = owned_quiz(request.user, pk)
    quiz.is_active = not quiz.is_active
    quiz.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f'Cuestionario {"activado" if quiz.is_active else "desactivado"}.')
    return redirect("quizzes:detail", pk=pk)


def question_form_context(form, formset, quiz, question=None):
    return {"form": form, "formset": formset, "quiz": quiz, "question": question, "page_title": "Editar pregunta" if question else "Agregar pregunta"}


def _question_post_data(request):
    """Convierte el radio único de la interfaz a los booleanos del formset."""
    if request.method != "POST":
        return None
    data = request.POST.copy()
    if "correct_component" not in data:
        return data
    try:
        total = int(data.get("options-TOTAL_FORMS", 0))
        selected = int(data["correct_component"])
    except (TypeError, ValueError):
        return data
    for index in range(total):
        data.pop(f"options-{index}-is_correct", None)
    if 0 <= selected < total:
        data[f"options-{selected}-is_correct"] = "on"
    return data


@login_required
def question_create(request, quiz_pk):
    quiz = owned_quiz(request.user, quiz_pk)
    question = Question(quiz=quiz)
    post_data = _question_post_data(request)
    form = QuestionForm(post_data, request.FILES or None, instance=question)
    initial = [{"order": number} for number in range(1, 5)] if request.method == "GET" else None
    formset = AnswerOptionFormSet(post_data, instance=question, initial=initial)
    form_valid = form.is_valid() if request.method == "POST" else False
    if form_valid:
        question.question_type = form.cleaned_data["question_type"]
        question.answer_case_sensitive = form.cleaned_data["answer_case_sensitive"]
    formset_valid = formset.is_valid() if form_valid else False
    if request.method == "POST" and form_valid and formset_valid:
        with transaction.atomic():
            question = form.save(commit=False)
            question.quiz = quiz
            question.order = (quiz.questions.aggregate(max_order=Max("order"))["max_order"] or 0) + 1
            question.save()
            formset.instance = question
            formset.save()
        messages.success(request, "Pregunta y alternativas agregadas correctamente.")
        return redirect("quizzes:detail", pk=quiz.pk)
    return render(request, "quizzes/question_form.html", question_form_context(form, formset, quiz))


@login_required
def question_update(request, pk):
    question = get_object_or_404(Question.objects.select_related("quiz"), pk=pk, quiz__teacher=request.user)
    post_data = _question_post_data(request)
    form = QuestionForm(post_data, request.FILES or None, instance=question)
    formset = AnswerOptionFormSet(post_data, instance=question)
    form_valid = form.is_valid() if request.method == "POST" else False
    if form_valid:
        question.question_type = form.cleaned_data["question_type"]
        question.answer_case_sensitive = form.cleaned_data["answer_case_sensitive"]
    formset_valid = formset.is_valid() if form_valid else False
    if request.method == "POST" and form_valid and formset_valid:
        with transaction.atomic():
            form.save()
            question.options.update(order=models.F("order") + 100)
            formset.save()
        messages.success(request, "Pregunta actualizada correctamente.")
        return redirect("quizzes:detail", pk=question.quiz_id)
    return render(request, "quizzes/question_form.html", question_form_context(form, formset, question.quiz, question))


@login_required
def question_delete(request, pk):
    question = get_object_or_404(Question.objects.select_related("quiz"), pk=pk, quiz__teacher=request.user)
    if request.method == "POST":
        quiz_id = question.quiz_id
        question.delete()
        _normalize_orders(Question.objects.filter(quiz_id=quiz_id))
        messages.success(request, "Pregunta eliminada correctamente.")
        return redirect("quizzes:detail", pk=quiz_id)
    return render(request, "quizzes/question_confirm_delete.html", {"question": question, "quiz": question.quiz})


def _normalize_orders(queryset):
    items = list(queryset.order_by("order", "id"))
    if not items:
        return
    offset = len(items) + max(item.order for item in items) + 10
    queryset.update(order=models.F("order") + offset)
    for number, item in enumerate(items, 1):
        Question.objects.filter(pk=item.pk).update(order=number)


@login_required
def question_reorder(request, pk, direction):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    question = get_object_or_404(Question.objects.select_related("quiz"), pk=pk, quiz__teacher=request.user)
    if direction not in {"up", "down"}:
        return redirect("quizzes:detail", pk=question.quiz_id)
    lookup = {"order__lt": question.order} if direction == "up" else {"order__gt": question.order}
    ordering = "-order" if direction == "up" else "order"
    neighbor = Question.objects.filter(quiz=question.quiz, **lookup).order_by(ordering).first()
    if neighbor:
        with transaction.atomic():
            original, target = question.order, neighbor.order
            Question.objects.filter(pk=question.pk).update(order=0)
            Question.objects.filter(pk=neighbor.pk).update(order=original)
            Question.objects.filter(pk=question.pk).update(order=target)
    return redirect("quizzes:detail", pk=question.quiz_id)
