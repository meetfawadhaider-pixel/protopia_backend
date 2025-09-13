import os
import datetime
import stripe

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import SubscriptionPlan, UserSubscription

# ────────────────────────────────────────────────────────────────────────────────
# Stripe keys / price map from environment
# ────────────────────────────────────────────────────────────────────────────────
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

PRICE_MAP = {
    "weekly": os.getenv("STRIPE_PRICE_WEEKLY", ""),
    "monthly": os.getenv("STRIPE_PRICE_MONTHLY", ""),
    "yearly": os.getenv("STRIPE_PRICE_YEARLY", ""),
}


def get_or_create_user_sub(user):
    sub, _ = UserSubscription.objects.get_or_create(user=user)
    return sub


# ────────────────────────────────────────────────────────────────────────────────
# Create a Stripe Checkout Session
# ────────────────────────────────────────────────────────────────────────────────
class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_key = (request.data.get("plan") or "").lower()
        if plan_key not in PRICE_MAP or not PRICE_MAP[plan_key]:
            return Response({"error": "Invalid plan"}, status=400)

        price_id = PRICE_MAP[plan_key]

        # Ensure DB plan record exists & matches price id
        plan, _ = SubscriptionPlan.objects.get_or_create(
            cadence=plan_key,
            defaults={"name": plan_key.capitalize(), "stripe_price_id": price_id},
        )
        if plan.stripe_price_id != price_id:
            plan.stripe_price_id = price_id
            plan.save(update_fields=["stripe_price_id"])

        # Customer
        sub = get_or_create_user_sub(request.user)
        customer_id = sub.stripe_customer_id
        if not customer_id:
            c = stripe.Customer.create(email=request.user.email)
            customer_id = c.id
            sub.stripe_customer_id = customer_id
            sub.save(update_fields=["stripe_customer_id"])

        # Frontend success/cancel
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        # IMPORTANT: include session id so we can verify on success page
        success_url = f"{frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{frontend_url}/payment/cancel"

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer=customer_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": request.user.id, "plan": plan_key},
            allow_promotion_codes=True,
        )
        return Response({"sessionUrl": session.url, "checkout_url": session.url})


# ────────────────────────────────────────────────────────────────────────────────
# Success-page activation fallback (works without webhooks)
# ────────────────────────────────────────────────────────────────────────────────
class ActivateSubscriptionView(APIView):
    """
    Frontend calls this on /payment/success with the ?session_id=... Stripe gives us.
    We verify the session with Stripe and mark the user's subscription active.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        if not session_id:
            return Response({"error": "session_id is required"}, status=400)

        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception:
            return Response({"error": "Invalid session_id"}, status=400)

        # Must be paid / completed
        if session.get("payment_status") not in ("paid", "no_payment_required"):
            return Response({"error": "Payment not completed yet"}, status=400)

        customer_id = session.get("customer")
        stripe_sub_id = session.get("subscription")
        plan_key = None
        if "metadata" in session and session["metadata"]:
            plan_key = (session["metadata"].get("plan") or "").lower()

        # Get or create user's DB sub
        sub = get_or_create_user_sub(request.user)
        sub.status = "active"
        if customer_id:
            sub.stripe_customer_id = customer_id
        if stripe_sub_id:
            sub.stripe_sub_id = stripe_sub_id

            # Pull current period end from Stripe subscription
            try:
                s = stripe.Subscription.retrieve(stripe_sub_id)
                end_ts = s["current_period_end"]
                sub.current_period_end = timezone.make_aware(
                    datetime.datetime.fromtimestamp(end_ts)
                )
            except Exception:
                pass

        # Attach plan if we know it
        if plan_key in PRICE_MAP:
            plan, _ = SubscriptionPlan.objects.get_or_create(
                cadence=plan_key,
                defaults={"name": plan_key.capitalize(), "stripe_price_id": PRICE_MAP[plan_key]},
            )
            sub.plan = plan

        sub.save()
        return Response({"status": "active"})


# ────────────────────────────────────────────────────────────────────────────────
# Webhook (optional in local dev; keep if you also test with Stripe CLI)
# ────────────────────────────────────────────────────────────────────────────────
@csrf_exempt
def stripe_webhook_view(request):
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        return HttpResponse(status=400)

    if event["type"] in (
        "checkout.session.completed",
        "invoice.paid",
        "customer.subscription.updated",
    ):
        data = event["data"]["object"]
        user_id = None
        plan_key = None

        if "metadata" in data:
            user_id = data["metadata"].get("user_id")
            plan_key = (data["metadata"].get("plan") or "").lower()

        # Fallback: look up by customer id
        if not user_id and "customer" in data:
            try:
                sub = UserSubscription.objects.get(stripe_customer_id=data["customer"])
                user_id = sub.user_id
            except UserSubscription.DoesNotExist:
                user_id = None

        if user_id:
            try:
                sub = UserSubscription.objects.get(user_id=user_id)
            except UserSubscription.DoesNotExist:
                return HttpResponse(status=200)

            stripe_sub_id = data.get("subscription")
            current_period_end = None
            if stripe_sub_id:
                s = stripe.Subscription.retrieve(stripe_sub_id)
                current_period_end = timezone.make_aware(
                    datetime.datetime.fromtimestamp(s["current_period_end"])
                )

            if plan_key in PRICE_MAP:
                plan, _ = SubscriptionPlan.objects.get_or_create(
                    cadence=plan_key,
                    defaults={"name": plan_key.capitalize(), "stripe_price_id": PRICE_MAP[plan_key]},
                )
                sub.plan = plan

            sub.status = "active"
            if stripe_sub_id:
                sub.stripe_sub_id = stripe_sub_id
            if current_period_end:
                sub.current_period_end = current_period_end
            sub.save()

    return HttpResponse(status=200)
