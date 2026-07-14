from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from quizzes.models import AnswerOption, Question, Quiz

from .models import Avatar, GameSession, Participant, ParticipantAnswer


class LiveGameBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user("teacher", password="secret-123")
        cls.other_teacher = User.objects.create_user("other", password="secret-123")
        cls.quiz = Quiz.objects.create(teacher=cls.teacher, title="Matemática")
        cls.question = Question.objects.create(quiz=cls.quiz, text="2 + 2", time_limit=20, points=1000, order=1)
        cls.options = [AnswerOption.objects.create(question=cls.question, text=text, is_correct=index == 1, order=index + 1) for index, text in enumerate(["3", "4", "5", "6"])]

    def make_game(self, **kwargs):
        defaults = {"quiz": self.quiz, "host": self.teacher, "pin": "123456"}
        defaults.update(kwargs)
        return GameSession.objects.create(**defaults)


class PinAndScoringTests(LiveGameBase):
    def test_pin_generation_is_six_digits_and_unique(self):
        with patch("livegames.models.random.randint", side_effect=[123456, 654321]):
            first = GameSession.create_with_unique_pin(quiz=self.quiz, host=self.teacher)
            second = GameSession.create_with_unique_pin(quiz=self.quiz, host=self.teacher)
        self.assertEqual(first.pin, "123456")
        self.assertEqual(second.pin, "654321")
        self.assertRegex(first.pin, r"^\d{6}$")

    def test_score_formula(self):
        self.assertEqual(ParticipantAnswer.calculate_points(self.question, False, 0), 0)
        self.assertEqual(ParticipantAnswer.calculate_points(self.question, True, 0), 1000)
        self.assertEqual(ParticipantAnswer.calculate_points(self.question, True, 10000), 750)
        self.assertEqual(ParticipantAnswer.calculate_points(self.question, True, 20000), 500)

    def test_server_uses_its_own_elapsed_time(self):
        started = timezone.now()
        game = self.make_game(status=GameSession.Status.QUESTION, current_question=self.question, question_started_at=started)
        participant = Participant.objects.create(game=game, nickname="Luna", session_identifier="session-a")
        answer = ParticipantAnswer.build_for_active_question(participant, self.options[1], now=started + timedelta(seconds=5))
        self.assertEqual(answer.response_time_ms, 5000)
        self.assertEqual(answer.points_earned, 875)
        with self.assertRaises(ValidationError):
            ParticipantAnswer.build_for_active_question(participant, self.options[1], now=started + timedelta(seconds=21))


class DiverseQuestionTypeTests(LiveGameBase):
    def active_participant(self, question):
        started = timezone.now()
        game = self.make_game(status=GameSession.Status.QUESTION, current_question=question, question_started_at=started)
        participant = Participant.objects.create(game=game, nickname="Tipo", session_identifier="session-type")
        return participant, started

    def test_true_false_is_evaluated_on_server(self):
        question = Question.objects.create(quiz=self.quiz, text="El Sol es una estrella", question_type=Question.Type.TRUE_FALSE, order=2)
        true = AnswerOption.objects.create(question=question, text="Verdadero", is_correct=True, order=1)
        AnswerOption.objects.create(question=question, text="Falso", order=2)
        participant, started = self.active_participant(question)
        answer = ParticipantAnswer.build_from_submission(participant, {"option": str(true.pk)}, now=started)
        self.assertTrue(answer.is_correct)

    def test_multiple_choice_requires_exact_set_of_correct_answers(self):
        self.options[2].is_correct = True
        self.options[2].save(update_fields=["is_correct"])
        participant, started = self.active_participant(self.question)
        correct = ParticipantAnswer.build_from_submission(
            participant,
            {"options": [str(self.options[1].pk), str(self.options[2].pk)]},
            now=started,
        )
        incomplete = ParticipantAnswer.build_from_submission(
            participant,
            {"options": [str(self.options[1].pk)]},
            now=started,
        )
        self.assertTrue(correct.is_correct)
        self.assertFalse(incomplete.is_correct)
        self.assertEqual(correct.structured_answer["selected_option_ids"], [self.options[1].pk, self.options[2].pk])

    def test_short_answer_accepts_multiple_normalized_variants(self):
        question = Question.objects.create(quiz=self.quiz, text="Capital del Perú", question_type=Question.Type.SHORT_ANSWER, order=2)
        AnswerOption.objects.create(question=question, text="Lima", order=1)
        AnswerOption.objects.create(question=question, text="Ciudad de los Reyes", order=2)
        participant, started = self.active_participant(question)
        answer = ParticipantAnswer.build_from_submission(participant, {"short_answer": "  LÍMA  "}, now=started)
        self.assertTrue(answer.is_correct)
        self.assertEqual(answer.text_answer, "LÍMA")

    def test_ordering_requires_exact_server_sequence(self):
        question = Question.objects.create(quiz=self.quiz, text="Ordena", question_type=Question.Type.ORDERING, order=2)
        options = [AnswerOption.objects.create(question=question, text=text, order=index) for index, text in enumerate(("Primero", "Segundo", "Tercero"), 1)]
        participant, started = self.active_participant(question)
        correct = ParticipantAnswer.build_from_submission(participant, {"ordered_ids": f"[{options[0].pk},{options[1].pk},{options[2].pk}]"}, now=started)
        incorrect = ParticipantAnswer.build_from_submission(participant, {"ordered_ids": f"[{options[2].pk},{options[1].pk},{options[0].pk}]"}, now=started)
        self.assertTrue(correct.is_correct)
        self.assertFalse(incorrect.is_correct)

    def test_matching_requires_one_to_one_pairs(self):
        question = Question.objects.create(quiz=self.quiz, text="Relaciona", question_type=Question.Type.MATCHING, order=2)
        peru = AnswerOption.objects.create(question=question, text="Perú", match_text="Lima", order=1)
        chile = AnswerOption.objects.create(question=question, text="Chile", match_text="Santiago", order=2)
        participant, started = self.active_participant(question)
        answer = ParticipantAnswer.build_from_submission(participant, {f"match_{peru.pk}": str(peru.pk), f"match_{chile.pk}": str(chile.pk)}, now=started)
        self.assertTrue(answer.is_correct)
        with self.assertRaises(ValidationError):
            ParticipantAnswer.build_from_submission(participant, {f"match_{peru.pk}": str(peru.pk), f"match_{chile.pk}": str(peru.pk)}, now=started)


class AnswerAndAccessTests(LiveGameBase):
    def setUp(self):
        self.started = timezone.now()
        self.game = self.make_game(status=GameSession.Status.QUESTION, current_question=self.question, question_started_at=self.started)
        self.participant = Participant.objects.create(game=self.game, nickname="Sol", session_identifier="session-sol")

    def test_one_answer_per_participant_and_question(self):
        answer = ParticipantAnswer.build_for_active_question(self.participant, self.options[1], now=self.started)
        answer.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ParticipantAnswer.build_for_active_question(self.participant, self.options[0], now=self.started).save()

    def test_option_must_belong_to_active_question(self):
        other = Question.objects.create(quiz=self.quiz, text="Otra", order=2)
        option = AnswerOption.objects.create(question=other, text="X", order=1)
        with self.assertRaises(ValidationError):
            ParticipantAnswer.build_for_active_question(self.participant, option, now=self.started)

    def test_other_teacher_cannot_open_host_or_results(self):
        self.client.force_login(self.other_teacher)
        self.assertEqual(self.client.get(reverse("livegames:host_room", args=[self.game.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("livegames:results", args=[self.game.pk])).status_code, 404)

    def test_projection_mode_requires_post_and_only_host_can_toggle_it(self):
        url = reverse("livegames:toggle_projection_mode", args=[self.game.pk])
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("livegames:host_room", args=[self.game.pk]))
        self.game.refresh_from_db()
        self.assertTrue(self.game.projection_mode)

        self.client.force_login(self.other_teacher)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.game.refresh_from_db()
        self.assertTrue(self.game.projection_mode)

    def test_projection_mode_hides_correct_markers_results_and_ranking(self):
        self.game.projection_mode = True
        self.game.save(update_fields=["projection_mode"])
        self.client.force_login(self.teacher)
        room_url = reverse("livegames:host_room", args=[self.game.pk])

        active_response = self.client.get(room_url)
        self.assertContains(active_response, "Resultados visibles", count=0)
        self.assertContains(active_response, "Modo proyección activado")
        self.assertContains(active_response, self.options[1].text)
        self.assertNotContains(active_response, "host-correct")

        self.game.status = GameSession.Status.RESULTS
        self.game.save(update_fields=["status"])
        results_response = self.client.get(room_url)
        self.assertContains(results_response, "Resultados ocultos")
        self.assertNotContains(results_response, "Resultados de la pregunta")
        self.assertNotContains(results_response, "Clasificación parcial")
        self.assertNotContains(results_response, self.participant.nickname)

    def test_host_only_sees_correct_answer_after_results_are_published(self):
        self.client.force_login(self.teacher)
        room_url = reverse("livegames:host_room", args=[self.game.pk])

        active_response = self.client.get(room_url)
        self.assertNotContains(active_response, "Respuesta correcta")
        self.assertNotContains(active_response, "host-correct")

        self.game.status = GameSession.Status.RESULTS
        self.game.save(update_fields=["status"])
        results_response = self.client.get(room_url)
        self.assertContains(results_response, "Respuesta correcta")
        self.assertContains(results_response, "result-row correct")

    def test_projection_mode_hides_short_answer_solutions(self):
        question = Question.objects.create(
            quiz=self.quiz,
            text="Palabra secreta",
            question_type=Question.Type.SHORT_ANSWER,
            order=2,
        )
        AnswerOption.objects.create(question=question, text="Respuesta reservada", order=1)
        self.game.current_question = question
        self.game.projection_mode = True
        self.game.save(update_fields=["current_question", "projection_mode"])
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("livegames:host_room", args=[self.game.pk]))
        self.assertContains(response, "La respuesta correcta se revelará al terminar")
        self.assertNotContains(response, "Respuesta reservada")

    def test_projection_mode_does_not_change_participant_results(self):
        session = self.client.session
        session["ready"] = True
        session.save()
        self.participant.session_identifier = session.session_key
        self.participant.save(update_fields=["session_identifier"])
        ParticipantAnswer.build_for_active_question(
            self.participant,
            self.options[1],
            now=self.started,
        ).save()
        self.game.status = GameSession.Status.RESULTS
        self.game.projection_mode = True
        self.game.save(update_fields=["status", "projection_mode"])
        response = self.client.get(reverse("livegames:participant_room", args=[self.game.pk]))
        self.assertContains(response, "¡Respuesta correcta!")

    def test_participant_access_is_bound_to_browser_session(self):
        session = self.client.session
        session["ready"] = True
        session.save()
        self.participant.session_identifier = session.session_key
        self.participant.save(update_fields=["session_identifier"])
        room_url = reverse("livegames:participant_room", args=[self.game.pk])
        self.assertEqual(self.client.get(room_url).status_code, 200)
        self.game.status = GameSession.Status.RESULTS
        self.game.save(update_fields=["status"])
        self.assertEqual(self.client.get(room_url).status_code, 200)
        self.game.status = GameSession.Status.FINISHED
        self.game.save(update_fields=["status"])
        self.assertEqual(self.client.get(room_url).status_code, 200)
        other_client = self.client_class()
        self.assertEqual(other_client.get(room_url).status_code, 404)

    def test_answer_endpoint_calculates_and_does_not_duplicate_score(self):
        session = self.client.session
        session["ready"] = True
        session.save()
        self.participant.session_identifier = session.session_key
        self.participant.save(update_fields=["session_identifier"])
        url = reverse("livegames:submit_answer", args=[self.game.pk])
        self.client.post(url, {"option": self.options[1].pk})
        self.participant.refresh_from_db()
        first_score = self.participant.score
        self.assertGreater(first_score, 0)
        self.client.post(url, {"option": self.options[1].pk})
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.score, first_score)
        self.assertEqual(ParticipantAnswer.objects.filter(participant=self.participant).count(), 1)

    def test_answer_endpoint_handles_missing_option_without_404(self):
        session = self.client.session
        session["ready"] = True
        session.save()
        self.participant.session_identifier = session.session_key
        self.participant.save(update_fields=["session_identifier"])
        url = reverse("livegames:submit_answer", args=[self.game.pk])
        response = self.client.post(url, {})
        self.assertRedirects(response, reverse("livegames:participant_room", args=[self.game.pk]))
        self.assertEqual(ParticipantAnswer.objects.filter(participant=self.participant).count(), 0)

    def test_answer_endpoint_accepts_multiple_selected_options(self):
        self.options[2].is_correct = True
        self.options[2].save(update_fields=["is_correct"])
        session = self.client.session
        session["ready"] = True
        session.save()
        self.participant.session_identifier = session.session_key
        self.participant.save(update_fields=["session_identifier"])
        response = self.client.post(
            reverse("livegames:submit_answer", args=[self.game.pk]),
            {"options": [self.options[1].pk, self.options[2].pk]},
        )
        self.assertRedirects(response, reverse("livegames:participant_room", args=[self.game.pk]))
        answer = ParticipantAnswer.objects.get(participant=self.participant)
        self.assertTrue(answer.is_correct)
        self.assertEqual(answer.structured_answer["selected_option_ids"], [self.options[1].pk, self.options[2].pk])

    def test_host_controls_full_state_flow(self):
        self.game.status = GameSession.Status.WAITING
        self.game.current_question = None
        self.game.question_started_at = None
        self.game.save()
        self.client.force_login(self.teacher)
        room_url = reverse("livegames:host_room", args=[self.game.pk])
        self.assertEqual(self.client.get(room_url).status_code, 200)
        for action, expected in (("start", GameSession.Status.QUESTION), ("results", GameSession.Status.RESULTS), ("next", GameSession.Status.FINISHED)):
            self.client.post(reverse("livegames:host_action", args=[self.game.pk, action]))
            self.game.refresh_from_db()
            self.assertEqual(self.game.status, expected)
            self.assertEqual(self.client.get(room_url).status_code, 200)
        self.assertEqual(self.client.get(reverse("livegames:results", args=[self.game.pk])).status_code, 200)


class AvatarSystemTests(LiveGameBase):
    def setUp(self):
        self.avatar = Avatar.objects.create(
            name="Zorro de prueba",
            slug="zorro-de-prueba",
            category=Avatar.Category.ANIMAL,
            symbol="🦊",
            background_color="#EA580C",
            order=999,
        )
        self.game = self.make_game(status=GameSession.Status.WAITING)

    def test_join_requires_an_active_avatar_and_preserves_it_on_reconnection(self):
        url = reverse("livegames:join_nickname", args=[self.game.pin])
        response = self.client.post(url, {"nickname": "Nova"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elige un avatar")
        self.assertFalse(Participant.objects.filter(game=self.game, nickname="Nova").exists())

        self.avatar.is_active = False
        self.avatar.save(update_fields=["is_active"])
        response = self.client.post(url, {"nickname": "Nova", "avatar": self.avatar.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no está disponible")

        self.avatar.is_active = True
        self.avatar.save(update_fields=["is_active"])
        with patch("livegames.views.broadcast") as broadcast_mock:
            response = self.client.post(url, {"nickname": "Nova", "avatar": self.avatar.pk})
        participant = Participant.objects.get(game=self.game, nickname="Nova")
        self.assertRedirects(response, reverse("livegames:participant_room", args=[self.game.pk]))
        self.assertEqual(participant.avatar, self.avatar)
        broadcast_payload = broadcast_mock.call_args.kwargs["avatar"]
        self.assertEqual(broadcast_payload["id"], self.avatar.pk)
        self.assertEqual(broadcast_payload["category"], Avatar.Category.ANIMAL)

        reconnect_response = self.client.get(url)
        self.assertRedirects(reconnect_response, reverse("livegames:participant_room", args=[self.game.pk]))
        participant.refresh_from_db()
        self.assertEqual(participant.avatar, self.avatar)

    def test_avatar_is_rendered_in_lobby_participant_rankings_history_and_results(self):
        session = self.client.session
        session["ready"] = True
        session.save()
        participant = Participant.objects.create(
            game=self.game,
            nickname="Luz",
            avatar=self.avatar,
            session_identifier=session.session_key,
            score=700,
        )
        avatar_label = f"Avatar {self.avatar.name}"

        participant_response = self.client.get(reverse("livegames:participant_room", args=[self.game.pk]))
        self.assertContains(participant_response, avatar_label)

        self.client.force_login(self.teacher)
        host_response = self.client.get(reverse("livegames:host_room", args=[self.game.pk]))
        self.assertContains(host_response, avatar_label)

        self.game.status = GameSession.Status.FINISHED
        self.game.save(update_fields=["status"])
        final_response = self.client.get(reverse("livegames:host_room", args=[self.game.pk]))
        self.assertContains(final_response, "Podio final")
        self.assertContains(final_response, avatar_label)
        history_response = self.client.get(reverse("livegames:history"))
        self.assertContains(history_response, avatar_label)
        results_response = self.client.get(reverse("livegames:results", args=[self.game.pk]))
        self.assertContains(results_response, avatar_label)

        participant.refresh_from_db()
        self.assertEqual(participant.avatar_id, self.avatar.pk)

    def test_seed_catalog_contains_all_categories(self):
        categories = set(Avatar.objects.filter(is_active=True).values_list("category", flat=True))
        self.assertTrue({Avatar.Category.ANIMAL, Avatar.Category.OBJECT, Avatar.Category.CHARACTER}.issubset(categories))
