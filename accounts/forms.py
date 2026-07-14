from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class TeacherRegistrationForm(UserCreationForm):
    first_name = forms.CharField(label="Nombres", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    email = forms.EmailField(label="Correo electrónico")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "username", "password1", "password2"]
        labels = {"username": "Nombre de usuario"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "first_name": "Ingresa tus nombres",
            "last_name": "Ingresa tus apellidos",
            "email": "docente@correo.com",
            "username": "Elige un nombre de usuario",
            "password1": "Ingresa una contraseña",
            "password2": "Repite la contraseña",
        }
        for name, field in self.fields.items():
            field.widget.attrs.update({"class": "form-control", "placeholder": placeholders[name]})

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta registrada con este correo.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
