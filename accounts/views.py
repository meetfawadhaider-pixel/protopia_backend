from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import authenticate

# Email + cache utils for verification codes
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
import random
import re

from .models import User
from .serializers import RegisterUserSerializer, ProfileSerializer
from assessments.models import Score, FinalScore

# Stripe webhook imports
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
try:
    import stripe
except ImportError:
    stripe = None

# Configure Stripe if available
if stripe:
    stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


# =========================
# Accounts / Admin
# =========================

# ✅ Register new user
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    serializer = RegisterUserSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User registered successfully."}, status=201)
    print("❌ Registration Validation Errors:", serializer.errors)
    return Response(serializer.errors, status=400)


# ✅ Profile endpoint (includes subscription info)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    serializer = ProfileSerializer(request.user)
    return Response(serializer.data)


# ✅ Admin: list all candidates + their scores
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_candidate_list(request):
    if request.user.role != "admin":
        return Response({"detail": "Access denied."}, status=403)

    candidates = User.objects.filter(role="candidate")
    results = []
    for c in candidates:
        scores = Score.objects.filter(user=c)
        final = FinalScore.objects.filter(user=c).first()

        result = {
            "id": c.id,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "email": c.email,
            "profession": c.profession,
            "gender": c.gender,
            "age_range": c.age_range,
            "subscription_type": c.subscription_type,
            "trait_scores": {}
        }

        for s in scores:
            result["trait_scores"][s.trait] = round(min(max(s.score, 0.5), 5.0), 2)

        if final:
            for trait, detail in final.top_traits.items():
                result["trait_scores"][trait] = round(min(max(detail["mcq_score"], 0.5), 5.0), 2)
                result["trait_scores"][f"{trait}_essay"] = round(min(max(detail["essay_score"], 0.5), 5.0), 2)

        results.append(result)

    return Response(results)


# ✅ Admin: delete candidate with password confirmation
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_user_with_password(request, user_id):
    if request.user.role != "admin":
        return Response({"detail": "Only admins can delete users."}, status=403)

    password = request.data.get("password")
    if not password:
        return Response({"detail": "Password required."}, status=400)

    admin = authenticate(email=request.user.email, password=password)
    if not admin:
        return Response({"detail": "Invalid password."}, status=401)

    try:
        user = User.objects.get(id=user_id)
        if user.role == "admin":
            return Response({"detail": "Cannot delete another admin."}, status=403)
        user.delete()
        return Response({"message": "User deleted successfully."}, status=200)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=404)


# =========================
# Email Verification (6-digit) for Register
# =========================

EMAIL_CODE_TTL_SECONDS = 10 * 60   # 10 minutes
RESEND_COOLDOWN_SECONDS = 60       # 60s cooldown
EMAIL_REGEX = re.compile(r"^\S+@\S+\.\S+$")


def _code_cache_key(email: str) -> str:
    return f"email_code:{email.lower()}"


def _cooldown_key(email: str) -> str:
    return f"email_code_cd:{email.lower()}"


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


@api_view(["POST"])
@permission_classes([AllowAny])
def send_code(request):
    """
    POST { "email": "user@example.com" }
    Sends a 6-digit code to the email and stores it in cache for 10 minutes.
    """
    email_raw = (request.data.get("email") or "").strip()
    if not EMAIL_REGEX.match(email_raw):
        return Response({"detail": "Invalid email."}, status=400)

    email = email_raw.lower()

    if cache.get(_cooldown_key(email)):
        return Response({"detail": "Please wait before requesting a new code."}, status=429)

    code = _generate_code()
    cache.set(_code_cache_key(email), code, timeout=EMAIL_CODE_TTL_SECONDS)
    cache.set(_cooldown_key(email), True, timeout=RESEND_COOLDOWN_SECONDS)

    subject = "Your Protopia verification code"
    message = f"Your verification code is: {code}\n\nIt expires in 10 minutes."
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", getattr(settings, "EMAIL_HOST_USER", None))

    try:
        send_mail(subject, message, from_email, [email_raw], fail_silently=False)
    except Exception as e:
        return Response({"detail": f"Failed to send email: {e}"}, status=500)

    return Response({"sent": True}, status=200)


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_code(request):
    """
    POST { "email": "user@example.com", "code": "123456" }
    Verifies the 6-digit code stored in cache.
    """
    email_raw = (request.data.get("email") or "").strip()
    code = (request.data.get("code") or "").strip()

    if not EMAIL_REGEX.match(email_raw) or len(code) != 6 or not code.isdigit():
        return Response({"detail": "Invalid email or code."}, status=400)

    email = email_raw.lower()

    stored = cache.get(_code_cache_key(email))
    if stored is None:
        return Response({"verified": False, "detail": "Code expired or not found."}, status=400)

    if code != stored:
        return Response({"verified": False, "detail": "Incorrect code."}, status=400)

    cache.delete(_code_cache_key(email))
    return Response({"verified": True}, status=200)


# =========================
# Forgot Password (6-digit)
# =========================

def _reset_cache_key(email: str) -> str:
    return f"pwd_reset_code:{email.lower()}"


def _reset_cooldown_key(email: str) -> str:
    return f"pwd_reset_cd:{email.lower()}"


@api_view(["POST"])
@permission_classes([AllowAny])
def password_send_code(request):
    """
    POST { "email": "user@example.com" }
    Sends a 6-digit password reset code to the email (valid 10 minutes).
    Requires that the email already exists in the system.
    """
    email_raw = (request.data.get("email") or "").strip()
    if not EMAIL_REGEX.match(email_raw):
        return Response({"detail": "Invalid email."}, status=400)

    email = email_raw.lower()

    if not User.objects.filter(email__iexact=email).exists():
        return Response({"detail": "No user found with this email."}, status=404)

    if cache.get(_reset_cooldown_key(email)):
        return Response({"detail": "Please wait before requesting a new code."}, status=429)

    code = _generate_code()
    cache.set(_reset_cache_key(email), code, timeout=EMAIL_CODE_TTL_SECONDS)
    cache.set(_reset_cooldown_key(email), True, timeout=RESEND_COOLDOWN_SECONDS)

    subject = "Your Protopia password reset code"
    message = f"Your password reset code is: {code}\n\nIt expires in 10 minutes."
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", getattr(settings, "EMAIL_HOST_USER", None))

    try:
        send_mail(subject, message, from_email, [email_raw], fail_silently=False)
    except Exception as e:
        return Response({"detail": f"Failed to send email: {e}"}, status=500)

    return Response({"sent": True}, status=200)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset(request):
    """
    POST { "email": "user@example.com", "code": "123456", "new_password": "secret123" }
    Verifies the code and updates the user's password.
    """
    email_raw = (request.data.get("email") or "").strip()
    code = (request.data.get("code") or "").strip()
    new_password = (request.data.get("new_password") or "").strip()

    if not EMAIL_REGEX.match(email_raw) or len(code) != 6 or not code.isdigit():
        return Response({"detail": "Invalid email or code."}, status=400)
    if len(new_password) < 6:
        return Response({"detail": "Password must be at least 6 characters."}, status=400)

    email = email_raw.lower()

    stored = cache.get(_reset_cache_key(email))
    if stored is None:
        return Response({"reset": False, "detail": "Code expired or not found."}, status=400)
    if code != stored:
        return Response({"reset": False, "detail": "Incorrect code."}, status=400)

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return Response({"reset": False, "detail": "No account found with this email."}, status=404)

    # Reject if new password equals current password
    if user.check_password(new_password):
        return Response(
            {"reset": False, "detail": "New password must be different from your current password."},
            status=400
        )

    if hasattr(user, "is_active") and not user.is_active:
        user.is_active = True

    user.set_password(new_password)
    user.save()

    test_user = authenticate(email=user.email, password=new_password)
    if not test_user:
        return Response(
            {"reset": False, "detail": "Password set but authentication failed. Contact support."},
            status=500
        )

    cache.delete(_reset_cache_key(email))
    return Response({"reset": True}, status=200)


# =========================
# Stripe Webhook (Invoice Email)
# =========================

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """
    Handles Stripe events and emails tax invoices after successful payment.
    Event(s): invoice.payment_succeeded (subscription invoices incl. first payment)
    """
    if stripe is None:
        return HttpResponse("Stripe not installed", status=501)

    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not endpoint_secret:
        return HttpResponse("Webhook secret not configured", status=500)

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=endpoint_secret,
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event.get("type") == "invoice.payment_succeeded":
        invoice = event["data"]["object"]  # type: ignore

        customer_email = invoice.get("customer_email")
        if not customer_email and invoice.get("customer"):
            try:
                cust = stripe.Customer.retrieve(invoice["customer"])
                customer_email = cust.get("email")
            except Exception:
                customer_email = None

        if customer_email:
            number = invoice.get("number") or ""
            amount = (invoice.get("total") or 0) / 100.0
            currency = (invoice.get("currency") or "usd").upper()
            hosted_url = invoice.get("hosted_invoice_url") or ""
            pdf_url = invoice.get("invoice_pdf") or ""
            status = invoice.get("status") or "paid"

            subject = f"Your Protopia Tax Invoice {number}".strip()
            body = (
                "Hi,\n\n"
                "Thank you for your subscription payment to Protopia.\n\n"
                f"Invoice number: {number or '—'}\n"
                f"Amount paid: {amount:.2f} {currency}\n"
                f"Status: {status}\n\n"
                "View your invoice online:\n"
                f"{hosted_url}\n\n"
                "Download the PDF:\n"
                f"{pdf_url}\n\n"
                "If you have any questions, reply to this email.\n\n"
                "— Protopia"
            )

            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", getattr(settings, "EMAIL_HOST_USER", None))
            try:
                send_mail(subject, body, from_email, [customer_email], fail_silently=False)
            except Exception as e:
                print("Invoice email send error:", e)

    return HttpResponse(status=200)
