from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import AnswerOptionFormSet
from .models import AnswerOption, Question, Quiz


class QuizPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner", password="secret-123")
        cls.other = User.objects.create_user("other", password="secret-123")
        cls.quiz = Quiz.objects.create(teacher=cls.owner, title="Privado")

    def test_only_owner_can_view_or_edit_quiz(self):
        self.client.force_login(self.other)
        for name in ("detail", "update", "delete", "toggle"):
            method = self.client.post if name == "toggle" else self.client.get
            self.assertEqual(method(reverse(f"quizzes:{name}", args=[self.quiz.pk])).status_code, 404)

    def test_list_only_contains_owned_quizzes(self):
        Quiz.objects.create(teacher=self.other, title="Del otro")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("quizzes:list"))
        self.assertContains(response, "Privado")
        self.assertNotContains(response, "Del otro")

    def test_owner_can_create_question_with_four_options(self):
        self.client.force_login(self.owner)
        url = reverse("quizzes:question_create", args=[self.quiz.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {
            "question_type": Question.Type.MULTIPLE_CHOICE,
            "text": "Capital del Perú", "time_limit": "30", "points": "1000",
            "options-TOTAL_FORMS": "4", "options-INITIAL_FORMS": "0",
            "options-MIN_NUM_FORMS": "4", "options-MAX_NUM_FORMS": "4",
        }
        for index, text in enumerate(("Lima", "Cusco", "Piura", "Tacna")):
            data[f"options-{index}-text"] = text
            data[f"options-{index}-order"] = str(index + 1)
        data["options-0-is_correct"] = "on"
        data["options-2-is_correct"] = "on"
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse("quizzes:detail", args=[self.quiz.pk]))
        question = self.quiz.questions.get()
        self.assertEqual(question.options.count(), 4)
        self.assertEqual(question.options.filter(is_correct=True).count(), 2)

    def test_owner_can_create_every_supported_question_type(self):
        self.client.force_login(self.owner)
        url = reverse("quizzes:question_create", args=[self.quiz.pk])
        cases = [
            (Question.Type.TRUE_FALSE, [("Verdadero", ""), ("Falso", "")], 0),
            (Question.Type.SHORT_ANSWER, [("Lima", ""), ("Ciudad de los Reyes", "")], None),
            (Question.Type.ORDERING, [("Primero", ""), ("Segundo", ""), ("Tercero", "")], None),
            (Question.Type.MATCHING, [("Perú", "Lima"), ("Chile", "Santiago")], None),
        ]
        for number, (question_type, components, correct_index) in enumerate(cases, 1):
            data = {
                "question_type": question_type,
                "text": f"Pregunta tipo {number}",
                "time_limit": "30",
                "points": "1000",
                # El navegador declara las cuatro filas iniciales, aunque oculte
                # y deshabilite las que no utiliza el tipo seleccionado.
                "options-TOTAL_FORMS": "4",
                "options-INITIAL_FORMS": "0",
                "options-MIN_NUM_FORMS": "0",
                "options-MAX_NUM_FORMS": "10",
            }
            for index, (text, match_text) in enumerate(components):
                data[f"options-{index}-text"] = text
                data[f"options-{index}-match_text"] = match_text
                data[f"options-{index}-order"] = str(index + 1)
                if index == correct_index:
                    data["correct_component"] = str(index)
            response = self.client.post(url, data)
            self.assertRedirects(response, reverse("quizzes:detail", args=[self.quiz.pk]))
        self.assertEqual(self.quiz.questions.count(), 4)
        self.assertTrue(all(question.is_valid_configuration() for question in self.quiz.questions.all()))

    def test_owner_can_edit_true_false_and_change_correct_answer(self):
        question = Question.objects.create(quiz=self.quiz, text="La Tierra es plana", question_type=Question.Type.TRUE_FALSE, order=1)
        true_option = AnswerOption.objects.create(question=question, text="Verdadero", is_correct=True, order=1)
        false_option = AnswerOption.objects.create(question=question, text="Falso", is_correct=False, order=2)
        self.client.force_login(self.owner)
        data = {
            "question_type": Question.Type.TRUE_FALSE,
            "text": question.text,
            "time_limit": "20",
            "points": "1000",
            "correct_component": "1",
            "options-TOTAL_FORMS": "2",
            "options-INITIAL_FORMS": "2",
            "options-MIN_NUM_FORMS": "0",
            "options-MAX_NUM_FORMS": "10",
            "options-0-id": str(true_option.pk),
            "options-0-text": "Verdadero",
            "options-0-match_text": "",
            "options-0-order": "1",
            "options-1-id": str(false_option.pk),
            "options-1-text": "Falso",
            "options-1-match_text": "",
            "options-1-order": "2",
        }
        response = self.client.post(reverse("quizzes:question_update", args=[question.pk]), data)
        self.assertRedirects(response, reverse("quizzes:detail", args=[self.quiz.pk]))
        true_option.refresh_from_db()
        false_option.refresh_from_db()
        self.assertFalse(true_option.is_correct)
        self.assertTrue(false_option.is_correct)


class AlternativeValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        teacher = User.objects.create_user("teacher", password="secret-123")
        cls.quiz = Quiz.objects.create(teacher=teacher, title="Ciencia")

    def formset(self, correct_indexes=(0,), total=4):
        data = {"options-TOTAL_FORMS": str(total), "options-INITIAL_FORMS": "0", "options-MIN_NUM_FORMS": "4", "options-MAX_NUM_FORMS": "4"}
        for index in range(total):
            data[f"options-{index}-text"] = f"Opción {index + 1}"
            data[f"options-{index}-order"] = str(index + 1)
            if index in correct_indexes:
                data[f"options-{index}-is_correct"] = "on"
        return AnswerOptionFormSet(data=data, instance=Question(quiz=self.quiz))

    def test_requires_exactly_four_options(self):
        formset = self.formset(total=3)
        self.assertFalse(formset.is_valid())
        self.assertIn("exactamente cuatro", str(formset.non_form_errors()))

    def test_multiple_choice_accepts_one_or_several_correct_options(self):
        self.assertFalse(self.formset(correct_indexes=()).is_valid())
        self.assertTrue(self.formset(correct_indexes=(2,)).is_valid())
        self.assertTrue(self.formset(correct_indexes=(0, 1)).is_valid())
        self.assertTrue(self.formset(correct_indexes=(0, 1, 2)).is_valid())
        self.assertTrue(self.formset(correct_indexes=(0, 1, 2, 3)).is_valid())

    def test_question_orders_are_unique_per_quiz(self):
        Question.objects.create(quiz=self.quiz, text="Uno", order=1)
        with self.assertRaises(Exception):
            Question.objects.create(quiz=self.quiz, text="Dos", order=1)

    def test_configuration_rules_change_by_question_type(self):
        short = Question.objects.create(quiz=self.quiz, text="Capital", question_type=Question.Type.SHORT_ANSWER, order=1)
        AnswerOption.objects.create(question=short, text="Lima", order=1)
        AnswerOption.objects.create(question=short, text="Ciudad de los Reyes", order=2)
        self.assertTrue(short.is_valid_configuration())

        matching = Question.objects.create(quiz=self.quiz, text="Relaciona", question_type=Question.Type.MATCHING, order=2)
        AnswerOption.objects.create(question=matching, text="Perú", match_text="Lima", order=1)
        AnswerOption.objects.create(question=matching, text="Chile", match_text="Santiago", order=2)
        self.assertTrue(matching.is_valid_configuration())
        matching.options.filter(order=2).update(match_text="Lima")
        self.assertFalse(matching.is_valid_configuration())
