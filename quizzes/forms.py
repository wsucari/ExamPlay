from django import forms

from .models import Quiz


class QuizForm(forms.ModelForm):
    """Formulario para crear y editar cuestionarios."""

    class Meta:
        model = Quiz
        fields = [
            "title",
            "description",
            "is_active",
        ]

        labels = {
            "title": "Título del cuestionario",
            "description": "Descripción",
            "is_active": "Cuestionario activo",
        }

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ejemplo: Metodología de la investigación",
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Describe brevemente el cuestionario",
                    "rows": 4,
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }