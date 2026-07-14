from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
import unicodedata


class Quiz(models.Model):
    """Cuestionario creado por un docente."""

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quizzes",
        verbose_name="Docente",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="Título",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Descripción",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Cuestionario"
        verbose_name_plural = "Cuestionarios"

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return self.questions.count()

    def is_ready_to_play(self):
        """Indica si todas las preguntas tienen una configuración válida."""
        questions = self.questions.prefetch_related("options")
        return bool(questions) and all(question.is_valid_configuration() for question in questions)


class Question(models.Model):
    """Pregunta perteneciente a un cuestionario."""

    class Type(models.TextChoices):
        MULTIPLE_CHOICE = "multiple_choice", "Opción múltiple"
        TRUE_FALSE = "true_false", "Verdadero o falso"
        SHORT_ANSWER = "short_answer", "Respuesta corta"
        ORDERING = "ordering", "Ordenamiento"
        MATCHING = "matching", "Relacionar columnas"

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="Cuestionario",
    )

    text = models.TextField(
        verbose_name="Pregunta",
    )

    question_type = models.CharField(
        max_length=24,
        choices=Type.choices,
        default=Type.MULTIPLE_CHOICE,
        db_index=True,
        verbose_name="Tipo de pregunta",
    )

    answer_case_sensitive = models.BooleanField(
        default=False,
        verbose_name="Distinguir mayúsculas en respuesta corta",
    )

    image = models.ImageField(
        upload_to="questions/",
        blank=True,
        null=True,
        verbose_name="Imagen",
    )

    time_limit = models.PositiveIntegerField(
        default=20,
        validators=[
            MinValueValidator(5),
            MaxValueValidator(300),
        ],
        verbose_name="Tiempo límite en segundos",
    )

    points = models.PositiveIntegerField(
        default=1000,
        validators=[
            MinValueValidator(100),
            MaxValueValidator(5000),
        ],
        verbose_name="Puntaje máximo",
    )

    order = models.PositiveIntegerField(
        default=1,
        verbose_name="Orden",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"
        constraints = [
            models.UniqueConstraint(fields=["quiz", "order"], name="unique_question_order_per_quiz"),
        ]

    def __str__(self):
        return f"{self.order}. {self.text[:60]}"

    @staticmethod
    def normalize_answer(value, case_sensitive=False):
        value = " ".join((value or "").strip().split())
        value = "".join(
            character for character in unicodedata.normalize("NFKD", value)
            if not unicodedata.combining(character)
        )
        return value if case_sensitive else value.casefold()

    def configuration_errors(self):
        options = list(self.options.all())
        count = len(options)
        texts = [option.text.strip().casefold() for option in options]
        if self.question_type == self.Type.MULTIPLE_CHOICE:
            if count != 4:
                return ["Debe tener exactamente cuatro alternativas."]
            correct_count = sum(option.is_correct for option in options)
            if correct_count < 1:
                return ["Debe tener al menos una alternativa correcta."]
        elif self.question_type == self.Type.TRUE_FALSE:
            if count != 2 or set(texts) != {"verdadero", "falso"}:
                return ["Debe contener únicamente Verdadero y Falso."]
            if sum(option.is_correct for option in options) != 1:
                return ["Debe marcar una respuesta correcta."]
        elif self.question_type == self.Type.SHORT_ANSWER:
            normalized = [self.normalize_answer(option.text, self.answer_case_sensitive) for option in options]
            if not 1 <= count <= 10:
                return ["Debe registrar entre una y diez respuestas válidas."]
            if len(set(normalized)) != count:
                return ["Las respuestas válidas no pueden repetirse."]
        elif self.question_type == self.Type.ORDERING:
            if not 2 <= count <= 10:
                return ["Debe registrar entre dos y diez elementos."]
        elif self.question_type == self.Type.MATCHING:
            matches = [option.match_text.strip().casefold() for option in options]
            if not 2 <= count <= 10 or any(not match for match in matches):
                return ["Debe registrar entre dos y diez parejas completas."]
            if len(set(matches)) != count:
                return ["Los elementos de la columna derecha no pueden repetirse."]
        if len(set(texts)) != count:
            return ["Los elementos no pueden repetirse."]
        return []

    def is_valid_configuration(self):
        return not self.configuration_errors()

    def correct_answer_display(self):
        options = list(self.options.all())
        if self.question_type in {self.Type.MULTIPLE_CHOICE, self.Type.TRUE_FALSE}:
            correct = next((option.text for option in options if option.is_correct), "")
            return correct
        if self.question_type == self.Type.SHORT_ANSWER:
            return " / ".join(option.text for option in options)
        if self.question_type == self.Type.ORDERING:
            return " → ".join(option.text for option in options)
        return "; ".join(f"{option.text} ↔ {option.match_text}" for option in options)


class AnswerOption(models.Model):
    """Alternativa de respuesta de una pregunta."""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name="Pregunta",
    )

    text = models.CharField(
        max_length=300,
        verbose_name="Alternativa",
    )

    match_text = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="Elemento relacionado",
    )

    is_correct = models.BooleanField(
        default=False,
        verbose_name="Es correcta",
    )

    order = models.PositiveIntegerField(
        default=1,
        verbose_name="Orden",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Alternativa"
        verbose_name_plural = "Alternativas"
        constraints = [
            models.UniqueConstraint(fields=["question", "order"], name="unique_option_order_per_question"),
        ]

    def __str__(self):
        return self.text
