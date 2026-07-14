from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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


class Question(models.Model):
    """Pregunta perteneciente a un cuestionario."""

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="Cuestionario",
    )

    text = models.TextField(
        verbose_name="Pregunta",
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

    def __str__(self):
        return f"{self.order}. {self.text[:60]}"


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

    def __str__(self):
        return self.text