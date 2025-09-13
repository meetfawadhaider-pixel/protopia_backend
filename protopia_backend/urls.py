from django.contrib import admin
from django.urls import path, include
from accounts import views as account_views  # <-- add this import

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/assessments/', include('assessments.urls')),
    path('api/stripe/webhook/', account_views.stripe_webhook),  # <-- NEW: Stripe webhook endpoint
]
