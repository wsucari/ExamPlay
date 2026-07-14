import json
import random

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Prefetch
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from quizzes.models import Quiz

from .forms import NicknameForm, PinForm
from .models import GameSession, Participant, ParticipantAnswer


def broadcast(game_id, event, **payload):
    async_to_sync(get_channel_layer().group_send)(
        f"game_{game_id}", {"type": "game.event", "event": event, **payload}
    )


def ensure_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def participant_for_request(request, game):
    return get_object_or_404(
        Participant.objects.select_related("avatar"),
        game=game,
        session_identifier=ensure_session_key(request),
    )


@login_required
def game_create(request):
    quizzes = Quiz.objects.filter(teacher=request.user, is_active=True).prefetch_related("questions__options")
    if request.method == "POST":
        quiz = get_object_or_404(quizzes, pk=request.POST.get("quiz"))
        if not quiz.is_ready_to_play():
            messages.error(request, "El cuestionario necesita al menos una pregunta válida con cuatro alternativas.")
        else:
            game = GameSession.create_with_unique_pin(quiz=quiz, host=request.user)
            messages.success(request, f"Partida creada con PIN {game.pin}.")
            return redirect("livegames:host_room", pk=game.pk)
    return render(request, "livegames/game_select.html", {"quizzes": quizzes})


@login_required
def host_room(request, pk):
    game = get_object_or_404(
        GameSession.objects.select_related("quiz", "current_question").prefetch_related("current_question__options"),
        pk=pk,
        host=request.user,
    )
    participants = game.participants.select_related("avatar").order_by("-score", "joined_at")
    display_options = []
    matching_right_options = []
    option_results = []
    answer_count = 0
    result_summary = {"correct": 0, "incorrect": 0}
    if game.current_question_id:
        display_options = list(game.current_question.options.all())
        if game.status == GameSession.Status.QUESTION:
            if game.current_question.question_type == game.current_question.Type.ORDERING:
                random.shuffle(display_options)
                if len(display_options) > 1 and all(
                    option.order == index for index, option in enumerate(display_options, 1)
                ):
                    display_options = display_options[1:] + display_options[:1]
            elif game.current_question.question_type == game.current_question.Type.MATCHING:
                matching_right_options = display_options[:]
                random.shuffle(matching_right_options)
                if len(matching_right_options) > 1 and matching_right_options == display_options:
                    matching_right_options = matching_right_options[1:] + matching_right_options[:1]
        current_answers = ParticipantAnswer.objects.filter(participant__game=game, question=game.current_question)
        if not game.projection_mode and game.current_question.question_type in {
            game.current_question.Type.MULTIPLE_CHOICE,
            game.current_question.Type.TRUE_FALSE,
        }:
            option_results = list(game.current_question.options.all())
            answers_for_count = list(current_answers)
            for option in option_results:
                option.response_count = sum(
                    option.id in answer.structured_answer.get("selected_option_ids", [])
                    or answer.selected_option_id == option.id
                    for answer in answers_for_count
                )
        answer_count = current_answers.count()
        if not game.projection_mode:
            result_summary = {
                "correct": current_answers.filter(is_correct=True).count(),
                "incorrect": current_answers.filter(is_correct=False).count(),
            }
    return render(request, "livegames/host_room.html", {
        "game": game,
        "participants": participants,
        "display_options": display_options,
        "matching_right_options": matching_right_options,
        "option_results": option_results,
        "answer_count": answer_count,
        "result_summary": result_summary,
    })


@login_required
def toggle_projection_mode(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    game = get_object_or_404(GameSession, pk=pk, host=request.user)
    game.projection_mode = not game.projection_mode
    game.save(update_fields=["projection_mode"])
    if game.projection_mode:
        messages.success(request, "Modo proyección activado: las soluciones y clasificaciones están ocultas.")
    else:
        messages.success(request, "Modo proyección desactivado: los resultados vuelven a estar visibles.")
    return redirect("livegames:host_room", pk=game.pk)


@login_required
def host_action(request, pk, action):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    with transaction.atomic():
        game = get_object_or_404(GameSession.objects.select_for_update().select_related("quiz", "current_question"), pk=pk, host=request.user)
        questions = list(game.quiz.questions.order_by("order", "id"))
        now = timezone.now()
        event = None
        if action == "start" and game.status == GameSession.Status.WAITING and questions and game.participants.exists() and game.quiz.is_ready_to_play():
            game.status = GameSession.Status.QUESTION
            game.current_question = questions[0]
            game.started_at = now
            game.question_started_at = now
            event = "game_started"
        elif action == "results" and game.status == GameSession.Status.QUESTION:
            game.status = GameSession.Status.RESULTS
            event = "results_published"
        elif action == "next" and game.status == GameSession.Status.RESULTS:
            current_index = next((i for i, question in enumerate(questions) if question.pk == game.current_question_id), -1)
            if current_index + 1 < len(questions):
                game.current_question = questions[current_index + 1]
                game.status = GameSession.Status.QUESTION
                game.question_started_at = now
                event = "question_started"
            else:
                game.status = GameSession.Status.FINISHED
                game.finished_at = now
                event = "game_finished"
        elif action == "finish" and game.status != GameSession.Status.FINISHED:
            game.status = GameSession.Status.FINISHED
            game.finished_at = now
            event = "game_finished"
        else:
            messages.error(request, "La acción no corresponde al estado actual de la partida.")
            return redirect("livegames:host_room", pk=pk)
        game.save()
    broadcast(game.pk, event, status=game.status)
    if event in {"results_published", "game_finished"}:
        broadcast(game.pk, "ranking_updated", status=game.status)
    return redirect("livegames:host_room", pk=pk)


def join_pin(request):
    form = PinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        game = GameSession.objects.filter(pin=form.cleaned_data["pin"]).first()
        if not game:
            form.add_error("pin", "No existe una partida con ese PIN.")
        elif game.status != GameSession.Status.WAITING:
            form.add_error("pin", "Esta partida ya comenzó o finalizó.")
        else:
            return redirect("livegames:join_nickname", pin=game.pin)
    return render(request, "livegames/join_pin.html", {"form": form})


def join_nickname(request, pin):
    game = get_object_or_404(GameSession, pin=pin, status=GameSession.Status.WAITING)
    session_key = ensure_session_key(request)
    existing = Participant.objects.filter(game=game, session_identifier=session_key).first()
    if existing:
        return redirect("livegames:participant_room", pk=game.pk)
    form = NicknameForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            participant = Participant.objects.create(
                game=game,
                nickname=form.cleaned_data["nickname"],
                avatar=form.cleaned_data["avatar"],
                session_identifier=session_key,
            )
        except IntegrityError:
            form.add_error("nickname", "Ese apodo ya está en uso en esta partida.")
        else:
            broadcast(
                game.pk,
                "participant_joined",
                nickname=participant.nickname,
                avatar={
                    "id": participant.avatar_id,
                    "name": participant.avatar.name,
                    "category": participant.avatar.category,
                    "symbol": participant.avatar.symbol,
                    "background_color": participant.avatar.background_color,
                },
            )
            return redirect("livegames:participant_room", pk=game.pk)
    avatars = form.fields["avatar"].queryset
    return render(request, "livegames/join_nickname.html", {
        "form": form,
        "game": game,
        "avatars": avatars,
        "selected_avatar_id": request.POST.get("avatar", ""),
    })


def participant_room(request, pk):
    game = get_object_or_404(GameSession.objects.select_related("quiz", "current_question"), pk=pk)
    participant = participant_for_request(request, game)
    answer = None
    if game.current_question_id:
        answer = ParticipantAnswer.objects.filter(participant=participant, question=game.current_question).select_related("selected_option").first()
    participants = list(game.participants.select_related("avatar").order_by("-score", "joined_at"))
    position = next((index for index, item in enumerate(participants, 1) if item.pk == participant.pk), None)
    options = list(game.current_question.options.all()) if game.current_question_id else []
    ordered_ids_json = "[]"
    right_options = []
    if game.current_question_id and not answer:
        if game.current_question.question_type == game.current_question.Type.ORDERING:
            shuffled = options[:]
            random.shuffle(shuffled)
            if len(shuffled) > 1 and shuffled == options:
                shuffled = shuffled[1:] + shuffled[:1]
            options = shuffled
            ordered_ids_json = json.dumps([option.id for option in options])
        elif game.current_question.question_type == game.current_question.Type.MATCHING:
            right_options = options[:]
            random.shuffle(right_options)
    return render(request, "livegames/participant_room.html", {
        "game": game,
        "participant": participant,
        "answer": answer,
        "options": options,
        "participants": participants,
        "position": position,
        "ordered_ids_json": ordered_ids_json,
        "right_options": right_options,
    })


def submit_answer(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        with transaction.atomic():
            game = get_object_or_404(GameSession.objects.select_for_update().select_related("current_question"), pk=pk)
            participant = participant_for_request(request, game)
            participant.game = game
            answer = ParticipantAnswer.build_from_submission(participant, request.POST)
            answer.save()
            Participant.objects.filter(pk=participant.pk).update(score=F("score") + answer.points_earned)
    except IntegrityError:
        messages.info(request, "Tu respuesta ya había sido registrada.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, "Respuesta recibida. Espera los resultados.")
        broadcast(game.pk, "answer_received")
    return redirect("livegames:participant_room", pk=pk)


@login_required
def game_history(request):
    games = (
        GameSession.objects.filter(host=request.user)
        .select_related("quiz")
        .annotate(participant_total=Count("participants"))
        .prefetch_related(Prefetch("participants", queryset=Participant.objects.select_related("avatar").order_by("joined_at")))
    )
    return render(request, "livegames/game_history.html", {"games": games})


@login_required
def game_results(request, pk):
    game = get_object_or_404(GameSession.objects.select_related("quiz"), pk=pk, host=request.user)
    participants = game.participants.select_related("avatar").prefetch_related("answers__question__options", "answers__selected_option").order_by("-score", "joined_at")
    return render(request, "livegames/game_results.html", {"game": game, "participants": participants})
