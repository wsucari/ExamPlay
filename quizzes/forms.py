from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import AnswerOption, Question, Quiz


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css)


class QuizForm(BootstrapModelForm):
    class Meta:
        model = Quiz
        fields = ["title", "description", "is_active"]
        labels = {"title": "Título del cuestionario", "description": "Descripción", "is_active": "Cuestionario activo"}
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Ejemplo: Historia del Perú", "autofocus": True}),
            "description": forms.Textarea(attrs={"placeholder": "Describe brevemente el cuestionario", "rows": 4}),
        }


class QuestionForm(BootstrapModelForm):
    class Meta:
        model = Question
        fields = ["question_type", "text", "image", "time_limit", "points", "answer_case_sensitive"]
        labels = {
            "question_type": "Tipo de pregunta",
            "text": "Enunciado",
            "image": "Imagen opcional",
            "time_limit": "Tiempo límite (segundos)",
            "points": "Puntaje máximo",
            "answer_case_sensitive": "Distinguir mayúsculas y minúsculas",
        }
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3, "autofocus": True}),
            "time_limit": forms.NumberInput(attrs={"min": 5, "max": 300}),
            "points": forms.NumberInput(attrs={"min": 100, "max": 5000}),
        }


class AnswerOptionForm(BootstrapModelForm):
    def has_changed(self):
        """Una fila adicional sin texto es vacía, aunque `order` tenga default."""
        text_key = self.add_prefix("text")
        if not self.instance.pk and not (self.data.get(text_key) or "").strip():
            return False
        return super().has_changed()

    class Meta:
        model = AnswerOption
        fields = ["text", "match_text", "is_correct", "order"]
        widgets = {
            "order": forms.HiddenInput(),
            "text": forms.TextInput(attrs={"placeholder": "Escribe un elemento"}),
            "match_text": forms.TextInput(attrs={"placeholder": "Escribe su pareja"}),
        }


class QuestionComponentsFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active = [form for form in self.forms if form.cleaned_data and not form.cleaned_data.get("DELETE", False) and form.cleaned_data.get("text", "").strip()]
        question_type = self.instance.question_type
        count = len(active)
        limits = {
            Question.Type.MULTIPLE_CHOICE: (4, 4),
            Question.Type.TRUE_FALSE: (2, 2),
            Question.Type.SHORT_ANSWER: (1, 10),
            Question.Type.ORDERING: (2, 10),
            Question.Type.MATCHING: (2, 10),
        }
        minimum, maximum = limits[question_type]
        if not minimum <= count <= maximum:
            if minimum == maximum:
                amount = {2: "dos", 4: "cuatro"}.get(minimum, str(minimum))
                raise forms.ValidationError(f"Este tipo requiere exactamente {amount} elementos.")
            raise forms.ValidationError(f"Este tipo requiere entre {minimum} y {maximum} elementos.")

        texts = [form.cleaned_data["text"].strip().casefold() for form in active]
        if len(set(texts)) != count:
            raise forms.ValidationError("Los elementos no pueden repetirse.")

        correct_count = sum(bool(form.cleaned_data.get("is_correct")) for form in active)
        if question_type == Question.Type.MULTIPLE_CHOICE and correct_count < 1:
            raise forms.ValidationError("Debes marcar al menos una respuesta correcta.")
        if question_type == Question.Type.TRUE_FALSE and correct_count != 1:
            raise forms.ValidationError("Debes marcar exactamente una respuesta correcta.")
        if question_type == Question.Type.TRUE_FALSE and set(texts) != {"verdadero", "falso"}:
            raise forms.ValidationError("Las opciones deben ser Verdadero y Falso.")
        if question_type == Question.Type.MATCHING:
            matches = [form.cleaned_data.get("match_text", "").strip().casefold() for form in active]
            if any(not match for match in matches):
                raise forms.ValidationError("Cada elemento debe tener una pareja en la columna derecha.")
            if len(set(matches)) != count:
                raise forms.ValidationError("Las parejas de la columna derecha no pueden repetirse.")

        for order, form in enumerate(active, 1):
            form.cleaned_data["order"] = order
            form.instance.order = order
            if question_type == Question.Type.SHORT_ANSWER:
                form.cleaned_data["is_correct"] = True
                form.instance.is_correct = True
            elif question_type in {Question.Type.ORDERING, Question.Type.MATCHING}:
                form.cleaned_data["is_correct"] = False
                form.instance.is_correct = False
            if question_type != Question.Type.MATCHING:
                form.cleaned_data["match_text"] = ""
                form.instance.match_text = ""


AnswerOptionFormSet = inlineformset_factory(
    Question,
    AnswerOption,
    form=AnswerOptionForm,
    formset=QuestionComponentsFormSet,
    extra=4,
    min_num=0,
    max_num=10,
    validate_max=True,
    can_delete=True,
)
