import stripe
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.conf import settings
from django.core.mail import send_mail

stripe.api_key = settings.STRIPE_SECRET_KEY

@csrf_exempt
def webhook(request):
    """
    Stripe webhook endpoint: /api/stripe/webhook/
    Sends an invoice email to the customer when invoice.payment_succeeded fires.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    if not endpoint_secret:
        print("[Stripe] Missing STRIPE_WEBHOOK_SECRET in settings.")
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=endpoint_secret
        )
    except ValueError as e:
        print(f"[Stripe] Invalid payload: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        print(f"[Stripe] Invalid signature: {e}")
        return HttpResponse(status=400)

    if event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]  # type: ignore

        # Determine email
        email = invoice.get("customer_email")
        if not email:
            cust_id = invoice.get("customer")
            if cust_id:
                try:
                    cust = stripe.Customer.retrieve(cust_id)
                    email = (cust or {}).get("email")
                except Exception as e:
                    print(f"[Stripe] Could not retrieve customer: {e}")

        amount_paid = (invoice.get("amount_paid") or 0) / 100.0
        currency = (invoice.get("currency") or "usd").upper()
        number = invoice.get("number") or invoice.get("id")
        hosted_url = invoice.get("hosted_invoice_url")
        pdf_url = invoice.get("invoice_pdf")

        subject = f"Your Protopia tax invoice — {number}"
        lines = [
            "Thank you for your payment.",
            f"Amount: {amount_paid:.2f} {currency}",
            ""
        ]
        if hosted_url:
            lines.append(f"Hosted invoice: {hosted_url}")
        if pdf_url:
            lines.append(f"PDF invoice: {pdf_url}")
        lines.append("")
        lines.append("If you have any questions, reply to this email.")
        body = "\n".join(lines)

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", getattr(settings, "EMAIL_HOST_USER", None))

        if email:
            try:
                send_mail(subject, body, from_email, [email], fail_silently=False)
                print(f"[Stripe] Invoice email SENT to {email} for invoice {number}")
            except Exception as e:
                print(f"[Stripe] Failed to send invoice email: {e}")
        else:
            print("[Stripe] No customer email on invoice; skipping email send.")
    else:
        print(f"[Stripe] Received event: {event['type']}")

    return HttpResponse(status=200)
