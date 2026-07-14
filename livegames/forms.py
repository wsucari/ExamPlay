from django import forms

from .models import Avatar


class PinForm(forms.Form):
    pin = forms.RegexField(
        regex=r"^\d{6}$",
        label="PIN de la partida",
        error_messages={"invalid": "Ingresa un PIN numérico de seis dígitos."},
        widget=forms.TextInput(attrs={"class": "form-control form-control-lg text-center", "inputmode": "numeric", "maxlength": 6, "placeholder": "000000", "autofocus": True}),
    )


class NicknameForm(forms.Form):
    nickname = forms.CharField(
        min_length=2,
        max_length=30,
        label="Tu apodo",
        widget=forms.TextInput(attrs={"class": "form-control form-control-lg text-center", "placeholder": "Ejemplo: Luna", "autocomplete": "off", "autofocus": True}),
    )
    avatar = forms.ModelChoiceField(
        queryset=Avatar.objects.none(),
        empty_label=None,
        widget=forms.HiddenInput(),
        error_messages={
            "required": "Elige un avatar para entrar a la partida.",
            "invalid_choice": "El avatar seleccionado no está disponible.",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["avatar"].queryset = Avatar.objects.filter(is_active=True)

    def clean_nickname(self):
        nickname = " ".join(self.cleaned_data["nickname"].split())
        if not nickname.replace(" ", "").isalnum():
            raise forms.ValidationError("Usa solo letras, números y espacios.")
        return nickname
