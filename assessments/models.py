from django.db import models
from django.conf import settings

# =========================
# Existing assessment models
# =========================

class Question(models.Model):
    text = models.TextField()
    trait = models.CharField(max_length=100)
    profession_tags = models.JSONField(default=list)
    age_group = models.CharField(max_length=20, default="all")
    gender_specific = models.CharField(max_length=10, blank=True, null=True)
    weight = models.FloatField(default=1.0)
    reverse_score = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text[:50]}... ({self.trait})"


class UserResponse(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.IntegerField()  # 1 to 5

    def __str__(self):
        return f"{self.user.username} - Q{self.question.id}: {self.answer}"


class Score(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    trait = models.CharField(max_length=100)
    score = models.FloatField()  # Out of 5

    def __str__(self):
        return f"{self.user.username} - {self.trait}: {self.score}"


class EssayResponse(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question_number = models.PositiveIntegerField()
    answer_text = models.TextField()
    typing_time_seconds = models.PositiveIntegerField()
    paste_detected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Essay Q{self.question_number} - {self.user.email[:15]}..."


class FinalScore(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    final_integrity_score = models.FloatField()  # Out of 100
    verdict = models.CharField(max_length=100)

    top_traits = models.JSONField(default=dict)
    # Stores only Top 5 traits for display:
    # {
    #   "Empathy": {"mcq_sub": "Sensitivity","essay_sub": "Compassion","mcq_score": 4.2,"essay_score": 4.8},
    #   ...
    # }

    raw_traits = models.JSONField(default=dict)
    # ✅ Stores all 10 validated traits for analysis and traceability.

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Final Score for {self.user.email[:15]}: {self.final_integrity_score}"


# =========================
# New: Question Pools
# =========================

class VRQuestion(models.Model):
    text = models.TextField()
    pillar_key = models.CharField(max_length=100)
    pillar_name = models.CharField(max_length=200)
    tags = models.JSONField(default=list)
    expected_tone = models.CharField(max_length=100, blank=True, null=True)
    rubric = models.JSONField(default=dict)

    def __str__(self):
        return f"VRQ({self.pillar_key}): {self.text[:50]}..."


class EssayPrompt(models.Model):
    text = models.TextField()
    pillar_key = models.CharField(max_length=100)
    pillar_name = models.CharField(max_length=200)
    tags = models.JSONField(default=list)
    rubric = models.JSONField(default=dict)

    def __str__(self):
        return f"Essay({self.pillar_key}): {self.text[:50]}..."


# =========================
# New: Payments & VR session tracking
# =========================

class SubscriptionPlan(models.Model):
    CADENCE_CHOICES = (("weekly", "Weekly"), ("monthly", "Monthly"), ("yearly", "Yearly"))
    name = models.CharField(max_length=50, unique=True)  # e.g., Weekly / Monthly / Yearly
    cadence = models.CharField(max_length=10, choices=CADENCE_CHOICES)
    stripe_price_id = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return f"{self.name} ({self.cadence})"


class UserSubscription(models.Model):
    STATUS_CHOICES = (("active", "Active"), ("incomplete", "Incomplete"), ("canceled", "Canceled"))
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="incomplete")
    stripe_customer_id = models.CharField(max_length=120, blank=True, null=True)
    stripe_sub_id = models.CharField(max_length=120, blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_active(self):
        return self.status == "active" and self.current_period_end is not None

    def __str__(self):
        return f"{getattr(self.user, 'email', self.user_id)} - {self.status}"


class VRSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    scenario = models.CharField(max_length=100, default="ethics-01")
    choices = models.JSONField(default=list)  # e.g. [{"key":"privacy","picked":"protect","ts":"..."}]
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"VRSession(user={self.user_id}, scenario={self.scenario})"
# =========================
# Flow Progress Tracking
# =========================
from django.conf import settings
from django.db import models

class AssessmentProgress(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED"
        MCQ_DONE = "MCQ_DONE"
        ESSAY_DONE = "ESSAY_DONE"
        VR_DONE = "VR_DONE"
        FINALIZED = "FINALIZED"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessment_progress"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED
    )
    essay_snapshot = models.JSONField(null=True, blank=True)  # essay traits/subtraits/ai_comment
    vr_score = models.FloatField(null=True, blank=True)       # 0–50 after VR complete

    def advance(self, next_status):
        order = [
            self.Status.NOT_STARTED,
            self.Status.MCQ_DONE,
            self.Status.ESSAY_DONE,
            self.Status.VR_DONE,
            self.Status.FINALIZED,
        ]
        if order.index(next_status) >= order.index(self.status):
            self.status = next_status
            self.save()

    def __str__(self):
        return f"{self.user_id} → {self.status}"
