
import mimetypes
import logging
import json

from django.http import FileResponse, request
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.core.mail import send_mail
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from google.oauth2 import id_token
from google.auth.transport import requests

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from rest_framework_simplejwt.tokens import RefreshToken

from jobs.ai_services import get_ai_job_recommendation

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    GoogleRegisterSerializer,
)

from .models import JobApplication, User

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    GoogleRegisterSerializer,
    ProfileUpdateSerializer,
)


def build_auth_user_payload(request, user):
    profile_photo_url = ""
    if getattr(user, "profile_photo", None):
        profile_photo_url = request.build_absolute_uri(reverse("profile-photo"))

    resume_url = ""
    if getattr(user, "resume", None):
        resume_url = request.build_absolute_uri(reverse("profile-resume"))

    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "date_of_birth": user.date_of_birth,
        "user_type": user.user_type,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "is_email_verified": user.is_email_verified,
        "phone": getattr(user, "phone", ""),
        "profile_photo_url": profile_photo_url,
        "profile_photo_name": (
            user.profile_photo.name.rsplit("/", 1)[-1]
            if getattr(user, "profile_photo", None) else ""
        ),
        "resume_url": resume_url,
        "resume_name": (
            user.resume.name.rsplit("/", 1)[-1]
            if getattr(user, "resume", None) else ""
        ),
    }


# =====================================================
# REGISTER
# =====================================================

class RegisterView(APIView):

    def post(self, request):

        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():

            user = serializer.save()

            send_mail(
                subject="Welcome to BuildCareer.ai ðŸŽ‰",

                message=f"""
Hello {user.full_name},

Welcome to BuildCareer.ai!

Your account has been successfully created.

Account Type:
{user.get_user_type_display()}

We are excited to have you with us.

Best regards,
BuildCareer.ai Team
""",

                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )

            return Response(
                {
                    "success": True,
                    "message": "Registration successful.",

                    "user": build_auth_user_payload(request, user),
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "success": False,
                "message": "Registration failed.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


# =====================================================
# LOGIN
# =====================================================

class LoginView(APIView):

    def post(self, request):
        print("LOGIN REQUEST RECEIVED")
        print("EMAIL RECEIVED:", request.data.get("email"))
        print("PASSWORD RECEIVED:", bool(request.data.get("password")))
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            data = dict(serializer.validated_data)
            user_payload = dict(data.get("user", {}))
            user = get_user_model().objects.filter(pk=user_payload.get("id")).first()
            if user:
                user_payload["profile_photo_url"] = (
                    request.build_absolute_uri(reverse("profile-photo"))
                    if getattr(user, "profile_photo", None) else ""
                )
                user_payload["resume_url"] = (
                    request.build_absolute_uri(reverse("profile-resume"))
                    if user.resume else ""
                )
                data["user"] = user_payload

            return Response(
                {
                    "success": True,
                    "message": "Login successful.",
                    **data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "success": False,
                "message": "Login failed.",
                "errors": serializer.errors,
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )


# =====================================================
# GOOGLE LOGIN
# =====================================================

class GoogleLoginView(APIView):

    def post(self, request):

        credential = request.data.get("credential")
        user_type = request.data.get("user_type")

        if not credential:

            return Response(
                {
                    "success": False,
                    "message": "Google credential is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if user_type not in ["job_seeker", "recruiter"]:

            return Response(
                {
                    "success": False,
                    "message": "Valid user_type is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            idinfo = id_token.verify_oauth2_token(
                credential,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

        except ValueError:

            return Response(
                {
                    "success": False,
                    "message": "Invalid Google credential."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        google_id = idinfo.get("sub")
        email = idinfo.get("email")
        email_verified = idinfo.get("email_verified", False)

        if not google_id or not email:

            return Response(
                {
                    "success": False,
                    "message": "Google account information is incomplete."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not email_verified:

            return Response(
                {
                    "success": False,
                    "message": "Google email is not verified."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        email = email.lower().strip()

        User = get_user_model()

        user = User.objects.filter(google_id=google_id).first()

        if not user:

            return Response(
                {
                    "success": False,
                    "message": "Google account is not registered. Please sign up first."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if user.user_type != user_type:

            return Response(
                {
                    "success": False,
                    "message": "This Google account is registered with a different account type."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_active:

            return Response(
                {
                    "success": False,
                    "message": "This account is inactive."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "success": True,
                "message": "Google login successful.",

                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },

                "user": build_auth_user_payload(request, user),
            },
            status=status.HTTP_200_OK
        )


# =====================================================
# GOOGLE REGISTER
# =====================================================

class GoogleRegisterView(APIView):

    def post(self, request):

        serializer = GoogleRegisterSerializer(data=request.data)

        if not serializer.is_valid():

            return Response(
                {
                    "success": False,
                    "message": "Google registration failed.",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        credential = serializer.validated_data.pop("credential")
        user_type = serializer.validated_data.get("user_type")

        try:

            idinfo = id_token.verify_oauth2_token(
                credential,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

        except ValueError:

            return Response(
                {
                    "success": False,
                    "message": "Invalid Google credential."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        google_id = idinfo.get("sub")
        google_email = idinfo.get("email")
        email_verified = idinfo.get("email_verified", False)

        google_first_name = idinfo.get("given_name", "")
        google_last_name = idinfo.get("family_name", "")

        if not google_id or not google_email:

            return Response(
                {
                    "success": False,
                    "message": "Google account information is incomplete."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not email_verified:

            return Response(
                {
                    "success": False,
                    "message": "Google email is not verified."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        google_email = google_email.lower().strip()

        User = get_user_model()

        if User.objects.filter(google_id=google_id).exists():

            return Response(
                {
                    "success": False,
                    "message": "This Google account is already registered. Please login with Google."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=google_email).exists():

            return Response(
                {
                    "success": False,
                    "message": "An account with this Google email already exists."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        first_name = google_first_name or serializer.validated_data.get("first_name", "")
        last_name = google_last_name or serializer.validated_data.get("last_name", "")

        full_name = f"{first_name} {last_name}".strip()

        serializer.validated_data.pop("first_name", None)
        serializer.validated_data.pop("last_name", None)

        password = serializer.validated_data.pop("password")

        user = User(
            email=google_email,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            google_id=google_id,
            is_email_verified=True,
            **serializer.validated_data
        )

        user.set_password(password)
        user.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "success": True,
                "message": "Google signup successful.",

                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },

                "user": build_auth_user_payload(request, user),
            },
            status=status.HTTP_201_CREATED
        )


# =====================================================
# PROFILE
# =====================================================

class ProfileView(APIView):

    permission_classes = [IsAuthenticated]

    @staticmethod
    def build_profile_photo_url(request, user):
        if not getattr(user, "profile_photo", None):
            return ""
        url = reverse("profile-photo")
        return request.build_absolute_uri(url) if request else url

    def get_profile_data(self, request):

        user = request.user
        profile_photo_url = self.build_profile_photo_url(request, user)

        return {
            "id": str(user.id),
            "full_name": user.full_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "user_type": user.user_type,
            "phone": user.phone,
            "date_of_birth": user.date_of_birth,

            # Job Seeker Profile
            "highest_qualification": user.highest_qualification,
            "college_name": user.college_name,
            "course_branch": user.course_branch,
            "graduation_year": user.graduation_year,

            "cgpa_percentage": (
                str(user.cgpa_percentage)
                if user.cgpa_percentage is not None
                else None
            ),

            "role_interested": user.role_interested,
            "skills": user.skills,
            "experience": user.experience,
            "location": user.location,

            # Recruiter Profile
            "company_name": user.company_name,
            "official_email": user.official_email,
            "company_website": user.company_website,

            # Resume
            "resume_url": (
                request.build_absolute_uri(
                    reverse("profile-resume")
                )
                if user.resume else ""
            ),

            "resume_name": (
                user.resume.name.rsplit("/", 1)[-1]
                if user.resume else ""
            ),

            # Profile Photo
            "profile_photo_url": profile_photo_url,
            "profile_photo_name": (
                user.profile_photo.name.rsplit("/", 1)[-1]
                if getattr(user, "profile_photo", None) else ""
            ),

            # Account Information
            "is_email_verified": user.is_email_verified,
            "terms_accepted": user.terms_accepted,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    # GET: Fetch logged-in user's profile
    def get(self, request):

        return Response(
            {
                "success": True,
                "message": "Profile fetched successfully.",
                "user": self.get_profile_data(request),
            },
            status=status.HTTP_200_OK,
        )

    # PUT: Update logged-in user's profile
    def put(self, request):

        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():

            serializer.save()

            return Response(
                {
                    "success": True,
                    "message": "Profile updated successfully.",
                    "user": self.get_profile_data(request),
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "success": False,
                "message": "Profile update failed.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # PATCH: Update selected profile fields
    def patch(self, request):

        return self.put(request)


# =====================================================
# PROFILE RESUME
# =====================================================

class ProfileResumeView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        candidate_id = request.query_params.get("candidate_id")

        user = (
            get_object_or_404(
                User,
                pk=candidate_id,
                user_type="job_seeker"
            )
            if candidate_id
            else request.user
        )

        if not user.resume:

            return Response(
                {"detail": "No resume has been uploaded."},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_owner = request.user.pk == user.pk

        can_view = (
            request.user.is_staff
            or is_owner
            or (
                request.user.user_type == "recruiter"
                and JobApplication.objects.filter(
                    applicant=user,
                    job__recruiter=request.user,
                ).exists()
            )
        )

        if not can_view:

            return Response(
                {"detail": "You are not allowed to view this resume."},
                status=status.HTTP_403_FORBIDDEN,
            )

        content_type = (
            mimetypes.guess_type(user.resume.name)[0]
            or "application/octet-stream"
        )

        response = FileResponse(
            user.resume.open("rb"),
            as_attachment=False,
            filename=user.resume.name.rsplit("/", 1)[-1],
            content_type=content_type,
        )

        response["X-Content-Type-Options"] = "nosniff"

        return response

    def post(self, request):

        if request.user.user_type != "job_seeker":

            return Response(
                {"detail": "Only job seekers can upload a resume."},
                status=status.HTTP_403_FORBIDDEN,
            )

        resume = request.FILES.get("resume")

        if not isinstance(resume, UploadedFile):

            return Response(
                {"resume": "Choose a resume file to upload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        extension = (
            resume.name.rsplit(".", 1)[-1].lower()
            if "." in resume.name else ""
        )

        if extension not in {"pdf", "doc", "docx"}:

            return Response(
                {"resume": "Resume must be a PDF, DOC, or DOCX file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if resume.size > 5 * 1024 * 1024:

            return Response(
                {"resume": "Resume must be 5 MB or smaller."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.resume = resume
        request.user.save(update_fields=["resume"])

        return Response(
            {
                "resume_url": request.build_absolute_uri(reverse("profile-resume")),
                "resume_name": request.user.resume.name.rsplit("/", 1)[-1],
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):

        if request.user.resume:
            request.user.resume.delete(save=False)
            request.user.resume = None
            request.user.save(update_fields=["resume"])

        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================
# PROFILE PHOTO
# =====================================================

class ProfilePhotoView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user

        if not getattr(user, "profile_photo", None):
            return Response(
                {"detail": "No profile photo has been uploaded."},
                status=status.HTTP_404_NOT_FOUND,
            )

        content_type = (
            mimetypes.guess_type(user.profile_photo.name)[0]
            or "application/octet-stream"
        )

        response = FileResponse(
            user.profile_photo.open("rb"),
            as_attachment=False,
            filename=user.profile_photo.name.rsplit("/", 1)[-1],
            content_type=content_type,
        )

        response["X-Content-Type-Options"] = "nosniff"

        return response

    def post(self, request):

        photo = request.FILES.get("profile_photo") or request.FILES.get("photo")

        if not isinstance(photo, UploadedFile):
            return Response(
                {"profile_photo": "Choose a photo file to upload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        extension = (
            photo.name.rsplit(".", 1)[-1].lower()
            if "." in photo.name else ""
        )

        if extension not in {"jpg", "jpeg", "png", "webp"}:
            return Response(
                {"profile_photo": "Photo must be a JPG, PNG, or WEBP file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if photo.size > 2 * 1024 * 1024:
            return Response(
                {"profile_photo": "Photo must be 2 MB or smaller."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if getattr(request.user, "profile_photo", None):
            request.user.profile_photo.delete(save=False)

        request.user.profile_photo = photo
        request.user.save(update_fields=["profile_photo"])

        profile_photo_url = request.build_absolute_uri(reverse("profile-photo"))

        return Response(
            {
                "profile_photo_url": profile_photo_url,
                "profile_photo_name": request.user.profile_photo.name.rsplit("/", 1)[-1],
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):

        if getattr(request.user, "profile_photo", None):
            request.user.profile_photo.delete(save=False)
            request.user.profile_photo = None
            request.user.save(update_fields=["profile_photo"])

        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================
# FORGOT PASSWORD
# =====================================================

class ForgotPasswordView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):

        email = request.data.get("email", "")

        if not isinstance(email, str):

            return Response(
                {
                    "success": False,
                    "message": "Invalid email."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        email = email.strip().lower()

        if not email:

            return Response(
                {
                    "success": False,
                    "message": "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        User = get_user_model()

        user = User.objects.filter(
            email=email,
            is_active=True
        ).first()

        if user:

            token_generator = PasswordResetTokenGenerator()

            uid = urlsafe_base64_encode(
                force_bytes(str(user.pk))
            )

            token = token_generator.make_token(user)

            reset_link = (
                f"{settings.FRONTEND_URL.rstrip('/')}"
                f"/reset-password/{uid}/{token}/"
            )

            subject = "Reset Your BuildCareer.ai Password"

            message = f"""
Hello {user.full_name},

We received a request to reset your BuildCareer.ai password.

Click the link below to create a new password:

{reset_link}

This link is valid for a limited time.

If you did not request this password reset,
please ignore this email.

Best regards,
BuildCareer.ai Team
"""

            try:

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

            except Exception:

                return Response(
                    {
                        "success": False,
                        "message": "Unable to send reset email. Please try again later."
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

        return Response(
            {
                "success": True,
                "message": "If an account exists with this email, a password reset link has been sent."
            },
            status=status.HTTP_200_OK
        )


# =====================================================
# RESET PASSWORD
# =====================================================

class ResetPasswordView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):

        uid = request.data.get("uid")
        token = request.data.get("token")
        password = request.data.get("password")
        confirm_password = request.data.get("confirm_password")

        if not all([uid, token, password, confirm_password]):

            return Response(
                {
                    "success": False,
                    "message": "All fields are required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if password != confirm_password:

            return Response(
                {
                    "success": False,
                    "message": "Passwords do not match."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            user_id = force_str(urlsafe_base64_decode(uid))

            User = get_user_model()

            user = User.objects.filter(
                pk=user_id,
                is_active=True
            ).first()

        except (ValueError, TypeError, OverflowError):

            user = None

        if not user:

            return Response(
                {
                    "success": False,
                    "message": "Invalid or expired reset link."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        token_generator = PasswordResetTokenGenerator()

        if not token_generator.check_token(user, token):

            return Response(
                {
                    "success": False,
                    "message": "Invalid or expired reset link."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            validate_password(password, user=user)

        except ValidationError as error:

            return Response(
                {
                    "success": False,
                    "message": "Password validation failed.",
                    "errors": error.messages
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(password)
        user.save(update_fields=["password"])

        return Response(
            {
                "success": True,
                "message": "Your password has been reset successfully. Please login."
            },
            status=status.HTTP_200_OK
        )


# =====================================================
# AI JOB CHATBOT - GEMINI
# =====================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_job_chat(request):

    try:

        user = request.user

        # Only job seekers can use job recommendations
        if user.user_type != "job_seeker":
            return Response(
                {
                    "success": False,
                    "message": "Only job seekers can use the AI job chatbot."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        user_message = request.data.get("message", "")

        if not isinstance(user_message, str) or not user_message.strip():
            return Response(
                {
                    "success": False,
                    "message": "Message cannot be empty."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        chat_history = request.data.get("history", [])
        if not isinstance(chat_history, list):
            return Response(
                {
                    "success": False,
                    "message": "Chat history must be a list."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        chat_history = [
            item
            for item in chat_history[-10:]
            if (
                isinstance(item, dict)
                and item.get("role") in {"user", "assistant"}
                and isinstance(item.get("text"), str)
            )
        ]

        # Send message to Gemini AI service
        ai_result = get_ai_job_recommendation(
            user_prompt=user_message.strip(),
            chat_history=chat_history,
            user=user
        )

        return Response(
            {
                "success": True,
                "reply": ai_result["reply"],
                "job_search": ai_result["job_search"],
            },
            status=status.HTTP_200_OK
        )

    except ImproperlyConfigured as error:
        logging.error("AI Job Chatbot configuration error: %s", error)
        return Response(
            {
                "success": False,
                "message": str(error)
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    except Exception:

        logging.exception("AI Job Chatbot Error")

        return Response(
            {
                "success": False,
                "message": "Something went wrong while processing your request."
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
