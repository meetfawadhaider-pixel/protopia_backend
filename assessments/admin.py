from django.contrib import admin
from .models import Question, UserResponse, Score, EssayResponse, FinalScore

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'trait')
    search_fields = ('text', 'trait')
    list_filter = ('trait',)

@admin.register(UserResponse)
class UserResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'question', 'answer')
    list_filter = ('question__trait', 'user')

@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'score', 'trait')
    list_filter = ('trait',)
    search_fields = ('user__email',)

@admin.register(EssayResponse)
class EssayResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'question_number', 'typing_time_seconds', 'paste_detected', 'created_at')
    list_filter = ('paste_detected', 'created_at')
    search_fields = ('user__email',)

@admin.register(FinalScore)
class FinalScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'final_integrity_score', 'verdict', 'created_at')
    list_filter = ('verdict', 'created_at')
    search_fields = ('user__email',)
    readonly_fields = ('top_traits',)
