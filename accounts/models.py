
from django_mongodb_backend.fields import ObjectIdAutoField
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.db import models


# =====================================================
# USER MANAGER
# =====================================================

class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):

        if not email:
            raise ValueError("Email is required.")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(
            email,
            password,
            **extra_fields
        )


# =====================================================
# CUSTOM USER MODEL
# =====================================================

class User(AbstractUser):

    USER_TYPE_CHOICES = [
        ("job_seeker", "Job Seeker"),
        ("recruiter", "Recruiter"),
    ]

    id = ObjectIdAutoField(primary_key=True)

    username = None

    objects = UserManager()

    email = models.EmailField(unique=True)

    google_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True
    )

    # COMMON FIELDS

    full_name = models.CharField(max_length=150)

    phone = models.CharField(max_length=20)

    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default="job_seeker"
    )

    # JOB SEEKER FIELDS

    date_of_birth = models.DateField(
        null=True,
        blank=True
    )

    highest_qualification = models.CharField(
        max_length=100,
        blank=True
    )

    college_name = models.CharField(
        max_length=200,
        blank=True
    )

    course_branch = models.CharField(
        max_length=150,
        blank=True
    )

    graduation_year = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    cgpa_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    role_interested = models.CharField(
        max_length=150,
        blank=True
    )

    skills = models.JSONField(
        default=list,
        blank=True
    )

    experience = models.CharField(
        max_length=100,
        blank=True
    )

    location = models.CharField(
        max_length=200,
        blank=True
    )

    # RECRUITER FIELDS

    company_name = models.CharField(
        max_length=200,
        blank=True
    )

    official_email = models.EmailField(
        blank=True
    )

    company_website = models.URLField(
        blank=True
    )

    profile_photo = models.FileField(
        upload_to="profile_photos/",
        blank=True,
        null=True
    )

    resume = models.FileField(
        upload_to="resumes/",
        blank=True,
        null=True
    )

    # ACCOUNT STATUS

    is_email_verified = models.BooleanField(default=False)

    terms_accepted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


# =====================================================
# JOB MODEL
# =====================================================

class Job(models.Model):

    id = ObjectIdAutoField(primary_key=True)

    JOB_TYPE_CHOICES = [
        ("Full-time", "Full-time"),
        ("Part-time", "Part-time"),
        ("Contract", "Contract"),
        ("Internship", "Internship"),
        ("Freelance", "Freelance"),
    ]

    WORKPLACE_CHOICES = [
        ("On-site", "On-site"),
        ("Remote", "Remote"),
        ("Hybrid", "Hybrid"),
    ]

    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
        ("Closed", "Closed"),
    ]

    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posted_jobs"
    )

    # BASIC INFORMATION

    title = models.CharField(max_length=200)

    company_name = models.CharField(max_length=200)

    company_logo = models.URLField(blank=True)

    category = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    location = models.CharField(max_length=200)

    job_type = models.CharField(
        max_length=30,
        choices=JOB_TYPE_CHOICES,
        default="Full-time"
    )

    workplace = models.CharField(
        max_length=20,
        choices=WORKPLACE_CHOICES,
        default="On-site"
    )

    # KEEP EXISTING DATABASE FIELD

    is_remote = models.BooleanField(default=False)

    # EXPERIENCE

    experience_level = models.CharField(
        max_length=100,
        default="Fresher"
    )

    # SALARY

    salary = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    salary_min = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    salary_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    salary_period = models.CharField(
        max_length=20,
        default="year"
    )

    # APPLICATION DETAILS

    application_deadline = models.DateField(
        null=True,
        blank=True
    )

    description = models.TextField()

    requirements = models.TextField(
        blank=True,
        default=""
    )

    skills = models.JSONField(
        default=list,
        blank=True
    )

    # JOB STATUS

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Active"
    )

    is_active = models.BooleanField(default=True)

    applicants_count = models.PositiveIntegerField(default=0)

    # TIMESTAMPS

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):

        # Keep workplace and is_remote consistent.
        self.is_remote = self.workplace == "Remote"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# =====================================================
# SAVED JOB MODEL
# =====================================================

class SavedJob(models.Model):

    id = ObjectIdAutoField(primary_key=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_jobs"
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="saved_by_users"
    )

    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "job")

    def __str__(self):
        return f"{self.user.email} - {self.job.title}"


class JobApplication(models.Model):

    STATUS_CHOICES = [
        ("Applied", "Applied"),
        ("CV Selected", "CV Selected"),
        ("1st Round Qualified", "1st Round Qualified"),
        ("2nd Round Qualified", "2nd Round Qualified"),
        ("Selected", "Selected"),
        ("Rejected", "Rejected"),
        ("Withdrawn", "Withdrawn"),
    ]

    id = ObjectIdAutoField(primary_key=True)

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_applications"
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications"
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="Applied"
    )

    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("applicant", "job")

    def __str__(self):
        return f"{self.applicant.email} - {self.job.title}"


class RecruiterInterview(models.Model):

    MODE_CHOICES = [
        ("Video", "Video"),
        ("On-site", "On-site"),
        ("Phone", "Phone"),
    ]

    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]

    id = ObjectIdAutoField(primary_key=True)

    application = models.ForeignKey(
        JobApplication,
        on_delete=models.CASCADE,
        related_name="interviews"
    )

    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recruiter_interviews"
    )

    scheduled_at = models.DateTimeField()

    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default="Video"
    )

    meeting_url = models.URLField(blank=True)

    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Scheduled"
    )

    score = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    feedback = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.application.applicant.email} - {self.scheduled_at}"


class RecruiterAssessment(models.Model):

    id = ObjectIdAutoField(primary_key=True)

    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recruiter_assessments"
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="assessments"
    )

    title = models.CharField(max_length=200)

    questions = models.JSONField(default=list)

    starts_at = models.DateTimeField()

    duration_minutes = models.PositiveSmallIntegerField(default=30)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
