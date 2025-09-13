from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    # 🔐 JWT Auth Routes
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 📧 Email Verification (Register)
    path('email/send-code/', views.send_code, name='email_send_code'),
    path('email/verify/', views.verify_code, name='email_verify'),

    # 🔁 Forgot Password
    path('password/send-code/', views.password_send_code, name='password_send_code'),
    path('password/reset/', views.password_reset, name='password_reset'),

    # 👤 User Management
    path('register/', views.register_user, name='register'),
    path('profile/', views.user_profile, name='profile'),

    # 🧠 Admin Dashboard
    path('admin/candidates/', views.admin_candidate_list, name='admin-candidate-list'),
    path('admin/delete/<int:user_id>/', views.delete_user_with_password, name='admin-delete-user'),
]
