
"""
Authentication and User APIs
BuildCareer.ai
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    LoginView,
    GoogleLoginView,
    GoogleRegisterView,
    ProfileView,
    ProfileResumeView,
    ProfilePhotoView,
    ForgotPasswordView,
    ResetPasswordView,
    ai_job_chat,
)


urlpatterns = [
    # User Authentication
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),

    # Google Authentication
    path("google/", GoogleLoginView.as_view(), name="google-login"),
    path("google/register/", GoogleRegisterView.as_view(), name="google-register"),

    # User Profile
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/resume/", ProfileResumeView.as_view(), name="profile-resume"),
    path("profile/photo/", ProfilePhotoView.as_view(), name="profile-photo"),

    # Password Management
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),

    # JWT Token
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # AI Job Chatbot
    path("ai-job-chat/", ai_job_chat, name="ai_job_chat"),
]
