from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AuthenticationTests(TestCase):
    def test_registration_normalizes_and_rejects_duplicate_email(self):
        payload = {
            "first_name": "Ana", "last_name": "Torres", "email": "ANA@EXAMPLE.COM",
            "username": "ana", "password1": "Clave-Segura-2026", "password2": "Clave-Segura-2026",
        }
        self.assertRedirects(self.client.post(reverse("accounts:register"), payload), reverse("accounts:login"))
        self.assertEqual(User.objects.get(username="ana").email, "ana@example.com")
        payload.update(username="ana2", email="ana@example.com")
        response = self.client.post(reverse("accounts:register"), payload)
        self.assertContains(response, "Ya existe una cuenta", status_code=200)

    def test_logout_only_accepts_post(self):
        user = User.objects.create_user("teacher", password="secret-123")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), reverse("core:home"))
