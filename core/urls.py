from django.urls import path
from .views import analyze_response

urlpatterns = [
    path('analyze/', analyze_response, name='analyze-response'),
]
