from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from collections import defaultdict
import random

from .models import (
    Question,
    UserResponse,
    Score,
    EssayResponse,
    FinalScore,
    AssessmentProgress,
    VRSession,  # <-- needed for reset
)
from .serializers import QuestionSerializer, EssayResponseSerializer
from .ai_analysis import analyze_essay

# ✅ Traits to be displayed only (scientifically validated)
DISPLAY_TRAITS = [
    "empathy",
    "ethical_reasoning",
    "authenticity",
    "critical_thinking",
    "clarity",
    "inclusiveness",
    "accountability",
]

# ---------- helpers ----------
def get_progress(user):
    prog, _ = AssessmentProgress.objects.get_or_create(user=user)
    return prog

# ---------- progress endpoint ----------
class ProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prog = get_progress(request.user)
        return Response({"status": prog.status})

# ---------- MCQ (Questions + Submit) ----------
class QuestionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # allow fetching even if NOT_STARTED
        strict = list(
            Question.objects.filter(
                age_group__in=["all", user.age_range],
                gender_specific__in=[None, "", user.gender],
                profession_tags__overlap=[user.profession],
            )
        )

        if len(strict) >= 20:
            selected = random.sample(strict, 20)
        else:
            fallback = list(
                Question.objects.filter(
                    age_group__in=["all", user.age_range],
                    gender_specific__in=[None, "", user.gender],
                )
            )
            combined = list(set(strict + fallback))
            if len(combined) >= 20:
                selected = random.sample(combined, 20)
            else:
                all_qs = list(Question.objects.all())
                remaining_needed = 20 - len(combined)
                additional = random.sample(all_qs, min(remaining_needed, len(all_qs)))
                selected = combined + additional

        if len(selected) < 20:
            return Response(
                {"message": "Not enough questions available in the database."},
                status=400,
            )

        serializer = QuestionSerializer(selected, many=True)
        return Response(serializer.data)

class SubmitAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        prog = get_progress(user)
        if prog.status not in [
            AssessmentProgress.Status.NOT_STARTED,
            AssessmentProgress.Status.MCQ_DONE,
        ]:
            return Response(
                {"message": "Out of order: MCQs already completed."}, status=409
            )

        responses = request.data.get("responses", {})
        if len(responses) != 20:
            return Response({"message": "All 20 questions must be answered."}, status=400)

        # reset MCQ layer
        Score.objects.filter(user=user).delete()
        UserResponse.objects.filter(user=user).delete()

        trait_scores = defaultdict(list)
        score_map = {
            "Strongly Disagree": 1,
            "Disagree": 2,
            "Neutral": 3,
            "Agree": 4,
            "Strongly Agree": 5,
        }

        for qid, ans in responses.items():
            try:
                question = Question.objects.get(id=int(qid))
            except Question.DoesNotExist:
                continue
            raw = score_map.get(ans, 3)
            if getattr(question, "reverse_score", False):
                raw = 6 - raw
            trait_scores[question.trait].append(raw * question.weight)
            UserResponse.objects.create(user=user, question=question, answer=raw)

        for trait, values in trait_scores.items():
            avg = round(min(sum(values) / max(len(values), 1), 5.0), 2)
            Score.objects.create(user=user, trait=trait, score=avg)

        prog.advance(AssessmentProgress.Status.MCQ_DONE)
        return Response({"message": "MCQ saved successfully.", "next": "ESSAY"})

# ---------- Essay (Submit only; no finalization here) ----------
class EssaySubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        prog = get_progress(user)
        if prog.status != AssessmentProgress.Status.MCQ_DONE:
            return Response({"message": "Out of order: complete MCQs first."}, status=409)

        serializer = EssayResponseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"message": "Invalid data", "errors": serializer.errors}, status=400)

        data = serializer.validated_data
        answers, timers, pasted = data["answers"], data["timers"], data["is_pasted"]

        # persist essay responses
        for i in range(3):
            EssayResponse.objects.create(
                user=user,
                question_number=i + 1,
                answer_text=answers[i],
                typing_time_seconds=timers[i],
                paste_detected=pasted[i],
            )

        # analyze essay
        ai_result = analyze_essay(answers, timers, pasted)
        essay_score = ai_result["final_ai_score"]   # 0–100
        all_traits = ai_result["traits"]            # 0–1 per trait
        subtrait_map = ai_result["subtraits"]
        ai_comment = ai_result["ai_comment"]

        # ensure MCQ exists
        mcq_scores = {s.trait: s.score for s in Score.objects.filter(user=user)}
        if not mcq_scores:
            return Response({"message": "MCQ data missing"}, status=400)

        # save essay snapshot for final combination after VR
        prog.essay_snapshot = {
            "essay_score": essay_score,
            "traits": all_traits,
            "subtraits": subtrait_map,
            "ai_comment": ai_comment,
        }
        prog.advance(AssessmentProgress.Status.ESSAY_DONE)

        return Response({"message": "Essay saved. Proceed to VR.", "next": "VR"})

# ---------- Finalization (called after VR completion) ----------
def finalize_result(user):
    prog = get_progress(user)
    if prog.status != AssessmentProgress.Status.VR_DONE:
        return None, Response({"message": "VR not completed."}, status=409)

    snap = prog.essay_snapshot or {}
    essay_score = snap.get("essay_score", 0)
    all_traits = snap.get("traits", {})
    subtrait_map = snap.get("subtraits", {})
    ai_comment = snap.get("ai_comment", "")

    mcq_scores = {s.trait: s.score for s in Score.objects.filter(user=user)}
    if not mcq_scores:
        return None, Response({"message": "MCQ data missing"}, status=400)

    if prog.vr_score is None:
        return None, Response({"message": "VR score missing"}, status=400)

    # Combine MCQ + Essay into top_5 (each trait max 10)
    combined_traits = {}
    for trait in DISPLAY_TRAITS:
        if trait not in subtrait_map:
            continue
        mcq_val = max(0.5, round(min(mcq_scores.get(trait, 0), 4.7), 2))
        essay_val = max(0.5, round(min(all_traits.get(trait, 0) * 5.0, 4.7), 2))
        total = round(min(mcq_val + essay_val, 10.0), 2)
        combined_traits[trait] = {
            "score": total,
            "mcq_score": mcq_val,
            "essay_score": essay_val,
            "mcq_subtrait": subtrait_map[trait][0],
            "essay_subtrait": subtrait_map[trait][1],
        }

    top_5 = dict(sorted(combined_traits.items(), key=lambda x: x[1]["score"], reverse=True)[:5])
    total_out_of_50 = sum(v["score"] for v in top_5.values())

    # Weights: MCQ+Essay -> up to 50; VR (0–50) -> 50
    part_mcq_essay = (total_out_of_50 / 50) * 50  # 0–50
    part_vr = (prog.vr_score / 50) * 50           # 0–50
    final_score = round(part_mcq_essay + part_vr, 2)

    if final_score >= 85:
        verdict = "Outstanding Integrity"
    elif final_score >= 70:
        verdict = "Strong Integrity"
    elif final_score >= 50:
        verdict = "Moderate Integrity"
    else:
        verdict = "Needs Improvement"

    fs, _ = FinalScore.objects.update_or_create(
        user=user,
        defaults={
            "final_integrity_score": final_score,
            "verdict": verdict,
            "top_traits": top_5,
        },
    )
    prog.advance(AssessmentProgress.Status.FINALIZED)
    return fs, None

class FinalResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prog = get_progress(request.user)
        if prog.status != AssessmentProgress.Status.FINALIZED:
            return Response({"message": "Final result not ready yet."}, status=409)
        fs = FinalScore.objects.filter(user=request.user).first()
        if not fs:
            return Response({"message": "Result missing."}, status=404)
        return Response(
            {
                "final_integrity_score": fs.final_integrity_score,
                "verdict": fs.verdict,
                "top_traits": fs.top_traits,
            }
        )

# ---------- Reset (allow retake) ----------
class ResetAssessmentView(APIView):
    """
    Wipes the current user's assessment data and resets progress to NOT_STARTED.
    Allows the same user to retake the entire assessment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        u = request.user

        # delete all user-scoped assessment artifacts
        UserResponse.objects.filter(user=u).delete()
        Score.objects.filter(user=u).delete()
        EssayResponse.objects.filter(user=u).delete()
        VRSession.objects.filter(user=u).delete()
        FinalScore.objects.filter(user=u).delete()

        # reset/initialize progress
        prog, _ = AssessmentProgress.objects.get_or_create(user=u)
        prog.status = AssessmentProgress.Status.NOT_STARTED
        prog.essay_snapshot = None
        prog.vr_score = None
        prog.save()

        return Response({"message": "Assessment reset. You can start again."})
