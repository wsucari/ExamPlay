import json
import random

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import IntegrityError, models
from django.db.models.functions import Lower
from django.utils import timezone

from quizzes.models import AnswerOption, Question, Quiz


class Avatar(models.Model):
    class Category(models.TextChoices):
        ANIMAL = "animal", "Animales"
        OBJECT = "object", "Objetos"
        CHARACTER = "character", "Personajes"

    name = models.CharField(max_length=50, unique=True, verbose_name="Nombre")
    slug = models.SlugField(max_length=60, unique=True)
    category = models.CharField(max_length=12, choices=Category.choices, db_index=True, verbose_name="Categoría")
    symbol = models.CharField(max_length=12, verbose_name="Símbolo")
    background_color = models.CharField(
        max_length=7,
        default="#6D28D9",
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Usa un color hexadecimal, por ejemplo #6D28D9.")],
        verbose_name="Color de fondo",
    )
    image = models.ImageField(upload_to="avatars/%Y/%m/", blank=True, verbose_name="Imagen personalizada")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Disponible")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="Orden")

    class Meta:
        ordering = ["category", "order", "name"]
        verbose_name = "Avatar"
        verbose_name_plural = "Avatares"

    def __str__(self):
        return self.name


class GameSession(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Sala de espera"
        QUESTION = "question", "Pregunta activa"
        RESULTS = "results", "Resultados"
        FINISHED = "finished", "Finalizada"

    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name="game_sessions", verbose_name="Cuestionario")
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosted_games", verbose_name="Docente anfitrión")
    pin = models.CharField(max_length=6, unique=True, db_index=True, verbose_name="PIN")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WAITING, db_index=True, verbose_name="Estado")
    current_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True, related_name="active_in_games", verbose_name="Pregunta actual")
    question_started_at = models.DateTimeField(null=True, blank=True, verbose_name="Inicio de pregunta")
    projection_mode = models.BooleanField(
        default=False,
        verbose_name="Modo proyección",
        help_text="Oculta soluciones, estadísticas y clasificaciones en la pantalla en vivo del docente.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de inicio")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de finalización")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Partida"
        verbose_name_plural = "Partidas"

    def __str__(self):
        return f"{self.quiz} · {self.pin}"

    def clean(self):
        if self.quiz_id and self.host_id and self.quiz.teacher_id != self.host_id:
            raise ValidationError("El anfitrión debe ser propietario del cuestionario.")
        if self.current_question_id and self.current_question.quiz_id != self.quiz_id:
            raise ValidationError("La pregunta actual no pertenece al cuestionario.")

    @classmethod
    def create_with_unique_pin(cls, *, quiz, host):
        """Genera un PIN de seis dígitos; la restricción UNIQUE resuelve carreras."""
        for _ in range(100):
            try:
                return cls.objects.create(quiz=quiz, host=host, pin=f"{random.randint(0, 999999):06d}")
            except IntegrityError:
                continue
        raise RuntimeError("No fue posible generar un PIN único.")


class Participant(models.Model):
    game = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name="participants", verbose_name="Partida")
    avatar = models.ForeignKey(
        Avatar,
        on_delete=models.PROTECT,
        related_name="participants",
        null=True,
        blank=True,
        verbose_name="Avatar",
        help_text="Puede estar vacío únicamente en participantes históricos creados antes del catálogo de avatares.",
    )
    nickname = models.CharField(max_length=30, verbose_name="Apodo")
    session_identifier = models.CharField(max_length=40, verbose_name="Identificador de sesión")
    score = models.PositiveIntegerField(default=0, verbose_name="Puntaje acumulado")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de ingreso")

    class Meta:
        ordering = ["-score", "joined_at"]
        verbose_name = "Participante"
        verbose_name_plural = "Participantes"
        constraints = [
            models.UniqueConstraint(Lower("nickname"), "game", name="unique_nickname_ci_per_game"),
            models.UniqueConstraint(fields=["game", "session_identifier"], name="unique_session_per_game"),
        ]

    def __str__(self):
        return f"{self.nickname} ({self.game.pin})"


class ParticipantAnswer(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="answers", verbose_name="Participante")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="participant_answers", verbose_name="Pregunta")
    selected_option = models.ForeignKey(AnswerOption, on_delete=models.PROTECT, related_name="participant_answers", null=True, blank=True, verbose_name="Alternativa seleccionada")
    text_answer = models.TextField(blank=True, verbose_name="Respuesta de texto")
    structured_answer = models.JSONField(default=dict, blank=True, verbose_name="Respuesta estructurada")
    is_correct = models.BooleanField(editable=False, verbose_name="Correcta")
    response_time_ms = models.PositiveIntegerField(editable=False, verbose_name="Tiempo de respuesta (ms)")
    points_earned = models.PositiveIntegerField(default=0, editable=False, verbose_name="Puntos obtenidos")
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de respuesta")

    class Meta:
        ordering = ["answered_at"]
        verbose_name = "Respuesta de participante"
        verbose_name_plural = "Respuestas de participantes"
        constraints = [
            models.UniqueConstraint(fields=["participant", "question"], name="unique_answer_per_participant_question"),
        ]

    def __str__(self):
        return f"{self.participant.nickname}: {self.question}"

    @staticmethod
    def calculate_points(question, is_correct, response_time_ms):
        """Correcta: entre 50% y 100% según velocidad; incorrecta: 0."""
        if not is_correct:
            return 0
        limit_ms = question.time_limit * 1000
        elapsed = min(max(response_time_ms, 0), limit_ms)
        speed_ratio = 1 - (elapsed / limit_ms)
        return round(question.points * (0.5 + 0.5 * speed_ratio))

    @property
    def response_display(self):
        question_type = self.question.question_type
        if question_type == Question.Type.MULTIPLE_CHOICE and self.structured_answer.get("selected_option_ids"):
            options = {option.id: option for option in self.question.options.all()}
            return ", ".join(options[option_id].text for option_id in self.structured_answer["selected_option_ids"] if option_id in options)
        if self.selected_option_id:
            return self.selected_option.text
        if question_type == Question.Type.SHORT_ANSWER:
            return self.text_answer
        options = {option.id: option for option in self.question.options.all()}
        if question_type == Question.Type.ORDERING:
            return " → ".join(options[option_id].text for option_id in self.structured_answer.get("ordered_ids", []) if option_id in options)
        if question_type == Question.Type.MATCHING:
            pairs = []
            for left_id, right_id in self.structured_answer.get("matches", {}).items():
                left = options.get(int(left_id))
                right = options.get(int(right_id))
                if left and right:
                    pairs.append(f"{left.text} ↔ {right.match_text}")
            return "; ".join(pairs)
        return "Sin respuesta"

    @classmethod
    def build_from_submission(cls, participant, data, now=None):
        """Valida y evalúa cualquier tipo de pregunta usando solo datos del servidor."""
        now = now or timezone.now()
        game = participant.game
        question = game.current_question
        if game.status != GameSession.Status.QUESTION or not question or not game.question_started_at:
            raise ValidationError("No hay una pregunta activa.")
        elapsed_ms = max(0, int((now - game.question_started_at).total_seconds() * 1000))
        if elapsed_ms > question.time_limit * 1000:
            raise ValidationError("El tiempo para responder terminó.")

        options = list(question.options.all())
        option_by_id = {option.id: option for option in options}
        selected_option = None
        text_answer = ""
        structured_answer = {}
        correct = False

        if question.question_type == Question.Type.MULTIPLE_CHOICE:
            if hasattr(data, "getlist"):
                raw_ids = data.getlist("options")
            else:
                raw_ids = data.get("options", [])
                if not isinstance(raw_ids, (list, tuple)):
                    raw_ids = [raw_ids] if raw_ids else []
            if not raw_ids and data.get("option"):
                raw_ids = [data.get("option")]
            try:
                selected_ids = [int(value) for value in raw_ids]
                selected_options = [option_by_id[option_id] for option_id in selected_ids]
            except (TypeError, ValueError, KeyError):
                raise ValidationError("Selecciona alternativas válidas.")
            if not selected_ids or len(set(selected_ids)) != len(selected_ids):
                raise ValidationError("Selecciona al menos una alternativa sin repetirla.")
            correct_ids = {option.id for option in options if option.is_correct}
            correct = set(selected_ids) == correct_ids
            selected_option = selected_options[0] if len(selected_options) == 1 else None
            structured_answer = {"selected_option_ids": selected_ids}
        elif question.question_type == Question.Type.TRUE_FALSE:
            try:
                selected_option = option_by_id[int(data.get("option", ""))]
            except (TypeError, ValueError, KeyError):
                raise ValidationError("Selecciona una alternativa válida.")
            correct = selected_option.is_correct
            structured_answer = {"selected_option_id": selected_option.id}
        elif question.question_type == Question.Type.SHORT_ANSWER:
            text_answer = " ".join(data.get("short_answer", "").strip().split())
            if not text_answer:
                raise ValidationError("Escribe una respuesta antes de enviarla.")
            if len(text_answer) > 300:
                raise ValidationError("La respuesta no puede superar 300 caracteres.")
            normalized = Question.normalize_answer(text_answer, question.answer_case_sensitive)
            accepted = {Question.normalize_answer(option.text, question.answer_case_sensitive) for option in options}
            correct = normalized in accepted
        elif question.question_type == Question.Type.ORDERING:
            raw_order = data.get("ordered_ids", "[]")
            if len(raw_order) > 1000:
                raise ValidationError("El orden enviado no es válido.")
            try:
                decoded_order = json.loads(raw_order)
                if not isinstance(decoded_order, list) or any(isinstance(value, bool) for value in decoded_order):
                    raise ValueError
                ordered_ids = [int(value) for value in decoded_order]
            except (TypeError, ValueError, json.JSONDecodeError):
                raise ValidationError("El orden enviado no es válido.")
            expected_ids = [option.id for option in options]
            if len(ordered_ids) != len(expected_ids) or set(ordered_ids) != set(expected_ids):
                raise ValidationError("Debes ordenar todos los elementos una sola vez.")
            structured_answer = {"ordered_ids": ordered_ids}
            correct = ordered_ids == expected_ids
        elif question.question_type == Question.Type.MATCHING:
            expected_ids = {option.id for option in options}
            matches = {}
            try:
                for option in options:
                    matches[str(option.id)] = int(data.get(f"match_{option.id}", ""))
            except (TypeError, ValueError):
                raise ValidationError("Relaciona todos los elementos antes de responder.")
            if set(matches.values()) != expected_ids:
                raise ValidationError("Cada elemento de la columna derecha debe utilizarse una sola vez.")
            structured_answer = {"matches": matches}
            correct = all(int(left_id) == right_id for left_id, right_id in matches.items())
        else:
            raise ValidationError("El tipo de pregunta no es compatible.")

        return cls(
            participant=participant,
            question=question,
            selected_option=selected_option,
            text_answer=text_answer,
            structured_answer=structured_answer,
            is_correct=correct,
            response_time_ms=elapsed_ms,
            points_earned=cls.calculate_points(question, correct, elapsed_ms),
        )

    @classmethod
    def build_for_active_question(cls, participant, option, now=None):
        return cls.build_from_submission(participant, {"option": option.pk}, now=now)
