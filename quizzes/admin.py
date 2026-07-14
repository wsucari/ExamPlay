from django.contrib import admin

from .models import AnswerOption, Question, Quiz
from .forms import QuestionComponentsFormSet


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    formset = QuestionComponentsFormSet
    extra = 2
    min_num = 0
    max_num = 10


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher", "is_active", "question_count", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("title", "description", "teacher__username", "teacher__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = (QuestionInline,)

    @admin.display(description="Preguntas")
    def question_count(self, obj):
        return obj.questions.count()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("short_text", "question_type", "quiz", "order", "time_limit", "points")
    list_filter = ("question_type", "quiz", "time_limit")
    search_fields = ("text", "quiz__title")
    ordering = ("quiz", "order")
    readonly_fields = ("created_at",)
    inlines = (AnswerOptionInline,)

    @admin.display(description="Pregunta")
    def short_text(self, obj):
        return obj.text[:70]


@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ("text", "match_text", "question", "is_correct", "order")
    list_filter = ("is_correct", "question__question_type", "question__quiz")
    search_fields = ("text", "match_text", "question__text")
