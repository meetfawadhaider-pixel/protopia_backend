from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import VRSession, VRQuestion, AssessmentProgress
from .views import get_progress, finalize_result


class VRStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Starts a VR interview session AFTER Essay step is done.
        Returns: { session_id, questions: [{id,text,pillar_key,pillar_name}, ...] }
        """
        prog = get_progress(request.user)
        if prog.status != AssessmentProgress.Status.ESSAY_DONE:
            return Response({"message": "Out of order: complete Essay first."}, status=409)

        count = int(request.data.get("count", 5))
        qs = list(VRQuestion.objects.order_by("?")[:max(1, count)])

        # Create a session; store nothing yet in choices (we’ll append answers later)
        session = VRSession.objects.create(user=request.user, scenario="ethics-01", choices=[])

        return Response({
            "session_id": session.id,
            "questions": [
                {
                    "id": q.id,
                    "text": q.text,
                    "pillar_key": getattr(q, "pillar_key", None),
                    "pillar_name": getattr(q, "pillar_name", None),
                } for q in qs
            ]
        })


class VRAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Append one answer to session. We persist into VRSession.choices (a JSON list).
        Body: { session_id, question_id, pillar_key, transcript, features }
        """
        session_id = request.data.get("session_id")
        question_id = request.data.get("question_id")
        transcript = (request.data.get("transcript") or "").strip()
        features = request.data.get("features") or {}
        pillar_key = request.data.get("pillar_key")

        if not session_id or not question_id:
            return Response({"message": "Missing session_id or question_id."}, status=400)

        try:
            session = VRSession.objects.get(id=session_id, user=request.user)
        except VRSession.DoesNotExist:
            return Response({"message": "VR session not found."}, status=404)

        if session.completed_at:
            return Response({"message": "Session already completed."}, status=409)

        # Append to choices list
        choices = list(session.choices or [])
        choices.append({
            "question_id": question_id,
            "pillar_key": pillar_key,
            "transcript": transcript,
            "features": features,
            "ts": timezone.now().isoformat(),
        })
        session.choices = choices
        session.save()

        return Response({"message": "Recorded"})


class VRCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Finalize session: compute vr_score (0–50), store in progress, move to VR_DONE,
        and finalize combined result (MCQ+Essay+VR) -> FINALIZED.
        Body: { session_id }
        """
        prog = get_progress(request.user)
        if prog.status != AssessmentProgress.Status.ESSAY_DONE:
            return Response({"message": "Out of order: Essay must be completed first."}, status=409)

        session_id = request.data.get("session_id")
        if not session_id:
            return Response({"message": "Missing session_id."}, status=400)

        try:
            session = VRSession.objects.get(id=session_id, user=request.user)
        except VRSession.DoesNotExist:
            return Response({"message": "VR session not found."}, status=404)

        if session.completed_at:
            # If already completed, re-use the stored vr_score if present in choices meta
            # but since VRSession.choices is a list, we didn't store a vr_score item before.
            # We'll just proceed to finalize_result guard below.
            pass

        answers = list(session.choices or [])[:5]

        # --- Simple heuristic scoring (0–10 per answer, cap 5 answers -> 50) ---
        def per_answer_score(item):
            transcript = (item.get("transcript") or "").strip()
            features = item.get("features") or {}
            words = len([w for w in transcript.split() if w.strip()])
            dur = float(features.get("_duration_sec") or 1.0)
            wps = float(features.get("speech_rate_wps") or (words / max(1.0, dur)))
            pauses = float(features.get("avg_pause_sec") or 0.5)

            score = 0.0
            # length
            if words >= 120:
                score += 6.0
            elif words >= 80:
                score += 5.0
            elif words >= 50:
                score += 4.0
            elif words >= 30:
                score += 3.0
            elif words >= 15:
                score += 2.0
            else:
                score += 1.0

            # fluency
            if 1.2 <= wps <= 3.2:
                score += 3.0
            elif 0.8 <= wps <= 4.0:
                score += 2.0
            elif 0.5 <= wps <= 5.0:
                score += 1.0

            # pauses
            if pauses < 0.8:
                score += 1.0
            elif pauses < 2.0:
                score += 0.5

            return max(0.0, min(10.0, score))

        per_scores = [per_answer_score(a) for a in answers]
        while len(per_scores) < 5:
            per_scores.append(0.0)

        vr_score = round(sum(per_scores), 2)  # 0–50

        # mark session complete
        session.completed_at = timezone.now()
        # append a light-weight summary record to choices for audit
        choices = list(session.choices or [])
        choices.append({"_summary": {"vr_score": vr_score, "answers_count": len(answers), "completed_at": session.completed_at.isoformat()}})
        session.choices = choices
        session.save()

        # advance progress & finalize
        prog.vr_score = vr_score
        prog.advance(AssessmentProgress.Status.VR_DONE)

        fs, error = finalize_result(request.user)
        if error:
            return error

        return Response({"message": "Interview finalized.", "vr_score": vr_score})
