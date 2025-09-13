from rest_framework import serializers
from .models import Question, EssayResponse, FinalScore

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id',
            'text',
            'trait',
            'profession_tags',
            'age_group',
            'gender_specific',
            'weight',
            'reverse_score'
        ]

# ✅ Serializer for Essay Submission
class EssayResponseSerializer(serializers.Serializer):
    answers = serializers.ListField(
        child=serializers.CharField(min_length=50),
        min_length=3,
        max_length=10
    )
    timers = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        min_length=3,
        max_length=10
    )
    is_pasted = serializers.ListField(
        child=serializers.BooleanField(),
        min_length=3,
        max_length=10
    )

    def validate(self, data):
        if not (len(data['answers']) == len(data['timers']) == len(data['is_pasted'])):
            raise serializers.ValidationError("Mismatch in answer, timer, and paste data.")
        return data

# ✅ (Optional) Serializer to return Final Scores in future APIs
class FinalScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinalScore
        fields = ['final_integrity_score', 'verdict', 'top_traits', 'raw_traits', 'created_at']
