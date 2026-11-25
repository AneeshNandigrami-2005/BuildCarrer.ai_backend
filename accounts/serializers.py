
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


# =====================================================
# REGISTER SERIALIZER
# =====================================================

class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    confirm_password = serializers.CharField(
        write_only=True
    )

    first_name = serializers.CharField(
        write_only=True
    )

    last_name = serializers.CharField(
        write_only=True
    )

    class Meta:
        model = User

        fields = [
            "user_type",
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "password",
            "confirm_password",

            # Job Seeker
            "highest_qualification",
            "college_name",
            "course_branch",
            "graduation_year",
            "cgpa_percentage",
            "role_interested",
            "skills",
            "experience",
            "location",

            # Recruiter
            "company_name",
            "official_email",
            "company_website",

            "terms_accepted",
        ]

    def validate_email(self, value):

        value = value.lower().strip()

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return value

    def validate(self, attrs):

        password = attrs.get("password")

        confirm_password = attrs.pop(
            "confirm_password",
            None
        )

        if password != confirm_password:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })

        if not attrs.get("terms_accepted"):
            raise serializers.ValidationError({
                "terms_accepted": (
                    "You must accept the Terms & Conditions."
                )
            })

        user_type = attrs.get("user_type")

        # Job Seeker Validation
        if user_type == "job_seeker":

            if not attrs.get("date_of_birth"):
                raise serializers.ValidationError({
                    "date_of_birth": "Date of birth is required."
                })

        # Recruiter Validation
        elif user_type == "recruiter":

            if not attrs.get("company_name"):
                raise serializers.ValidationError({
                    "company_name": "Company name is required."
                })

            if not attrs.get("official_email"):
                raise serializers.ValidationError({
                    "official_email": "Official email is required."
                })

        else:
            raise serializers.ValidationError({
                "user_type": "Invalid user type."
            })

        return attrs

    def create(self, validated_data):

        password = validated_data.pop("password")

        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")

        full_name = f"{first_name} {last_name}".strip()

        user = User(
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            **validated_data
        )

        user.set_password(password)
        user.save()

        return user


# =====================================================
# LOGIN SERIALIZER
# =====================================================


class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):

        email = attrs["email"].lower().strip()
        password = attrs["password"]

        # Find user using email
        user = User.objects.filter(
            email__iexact=email
        ).first()

        if not user:
            raise serializers.ValidationError({
                "detail": "Invalid email or password."
            })

        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError({
                "detail": "Invalid email or password."
            })

        # Check active account
        if not user.is_active:
            raise serializers.ValidationError({
                "detail": "This account is inactive."
            })

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),

            "user": {
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
                "phone": user.phone,
                "resume_name": (
                    user.resume.name.rsplit("/", 1)[-1]
                    if user.resume else ""
                ),
                "profile_photo_name": (
                    user.profile_photo.name.rsplit("/", 1)[-1]
                    if getattr(user, "profile_photo", None)
                    else ""
                ),
            },
        }


# =====================================================
# GOOGLE REGISTER SERIALIZER
# =====================================================

class GoogleRegisterSerializer(serializers.Serializer):

    credential = serializers.CharField(
        write_only=True
    )

    user_type = serializers.ChoiceField(
        choices=[
            ("job_seeker", "Job Seeker"),
            ("recruiter", "Recruiter"),
        ]
    )

    first_name = serializers.CharField()
    last_name = serializers.CharField()

    phone = serializers.CharField()

    date_of_birth = serializers.DateField(
        required=False,
        allow_null=True
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    confirm_password = serializers.CharField(
        write_only=True
    )

    # Job Seeker
    highest_qualification = serializers.CharField(
        required=False,
        allow_blank=True
    )

    college_name = serializers.CharField(
        required=False,
        allow_blank=True
    )

    course_branch = serializers.CharField(
        required=False,
        allow_blank=True
    )

    graduation_year = serializers.IntegerField(
        required=False,
        allow_null=True
    )

    cgpa_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True
    )

    role_interested = serializers.CharField(
        required=False,
        allow_blank=True
    )

    skills = serializers.ListField(
        required=False
    )

    experience = serializers.CharField(
        required=False,
        allow_blank=True
    )

    location = serializers.CharField(
        required=False,
        allow_blank=True
    )

    # Recruiter
    company_name = serializers.CharField(
        required=False,
        allow_blank=True
    )

    official_email = serializers.EmailField(
        required=False,
        allow_blank=True
    )

    company_website = serializers.URLField(
        required=False,
        allow_blank=True
    )

    terms_accepted = serializers.BooleanField()

    def validate(self, attrs):

        password = attrs.get("password")

        confirm_password = attrs.pop(
            "confirm_password",
            None
        )

        if password != confirm_password:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })

        if not attrs.get("terms_accepted"):
            raise serializers.ValidationError({
                "terms_accepted": (
                    "You must accept the Terms & Conditions."
                )
            })

        user_type = attrs.get("user_type")

        # Job Seeker Validation
        if user_type == "job_seeker":

            if not attrs.get("date_of_birth"):
                raise serializers.ValidationError({
                    "date_of_birth": "Date of birth is required."
                })

        # Recruiter Validation
        elif user_type == "recruiter":

            if not attrs.get("company_name"):
                raise serializers.ValidationError({
                    "company_name": "Company name is required."
                })

            if not attrs.get("official_email"):
                raise serializers.ValidationError({
                    "official_email": "Official email is required."
                })

        else:
            raise serializers.ValidationError({
                "user_type": "Invalid user type."
            })

        return attrs


# =====================================================
# PROFILE UPDATE SERIALIZER
# =====================================================

class ProfileUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User

        fields = [
            "first_name",
            "last_name",
            "phone",
            "date_of_birth",
            "highest_qualification",
            "college_name",
            "course_branch",
            "graduation_year",
            "cgpa_percentage",
            "role_interested",
            "skills",
            "experience",
            "location",
            "company_name",
            "official_email",
            "company_website",
        ]

    def update(self, instance, validated_data):

        # Update only submitted fields
        for field, value in validated_data.items():
            setattr(instance, field, value)

        # Automatically update full name
        instance.full_name = (
            f"{instance.first_name} {instance.last_name}"
        ).strip()

        instance.save()

        return instance
