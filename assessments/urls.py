from django.urls import path
from . import views
from .views_payments import (
    CreateCheckoutSessionView,
    stripe_webhook_view,
    ActivateSubscriptionView,   # ✅ add this import
)
from .views_vr import VRStartView, VRAnswerView, VRCompleteView
from .views import ProgressView, FinalResultView, ResetAssessmentView

urlpatterns = [
    # 🔹 Assessment endpoints
    path('questions/', views.QuestionListView.as_view(), name='question-list'),
    path('submit/', views.SubmitAnswersView.as_view(), name='submit-answers'),
    path('essay-submit/', views.EssaySubmitView.as_view(), name='essay-submit'),

    # 🔹 Payment endpoints
    path('pay/create-checkout-session/', CreateCheckoutSessionView.as_view(), name='create-checkout-session'),
    path('pay/activate/', ActivateSubscriptionView.as_view(), name='activate-subscription'),  # ✅ new
    path('pay/webhook/', stripe_webhook_view, name='stripe-webhook'),

    # 🔹 VR interview endpoints
    path('vr/start/', VRStartView.as_view(), name='vr-start'),
    path('vr/answer/', VRAnswerView.as_view(), name='vr-answer'),
    path('vr/complete/', VRCompleteView.as_view(), name='vr-complete'),

    # 🔹 Flow progress + final result
    path('progress/', ProgressView.as_view(), name='progress'),
    path('final/', FinalResultView.as_view(), name='final-result'),

    # 🔹 Reset (allow user to retake the entire assessment)
    path('reset/', ResetAssessmentView.as_view(), name='reset-assessment'),
]
