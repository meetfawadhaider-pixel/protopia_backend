from rest_framework import serializers
from .models import User
from assessments.models import Score, UserSubscription


# ✅ Serializer for user registration
class RegisterUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "password",
            "role",
            "profession",
            "gender",
            "age_range",
            "subscription_type",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


# ✅ Candidate listing with trait scores (for Admin dashboard)
class CandidateScoreSerializer(serializers.ModelSerializer):
    trait_scores = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "role",
            "profession",
            "gender",
            "age_range",
            "subscription_type",
            "trait_scores",
        ]

    def get_trait_scores(self, user):
        scores = Score.objects.filter(user=user)
        return {s.trait: s.score for s in scores}


# ✅ Subscription mini serializer
class SubscriptionMiniSerializer(serializers.ModelSerializer):
    plan = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = ("status", "current_period_end", "plan")

    def get_plan(self, obj):
        if obj and obj.plan:
            return {"name": obj.plan.name, "cadence": obj.plan.cadence}
        return None


# ✅ Profile serializer (fix: compute subscription from UserSubscription)
class ProfileSerializer(serializers.ModelSerializer):
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "role",
            "profession",
            "gender",
            "age_range",
            "subscription_type",
            "date_joined",
            "subscription",
        ]

    def get_subscription(self, user):
        sub = UserSubscription.objects.filter(user=user).first()
        return SubscriptionMiniSerializer(sub).data if sub else None
