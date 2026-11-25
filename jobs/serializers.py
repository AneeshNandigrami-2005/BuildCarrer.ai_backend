
from rest_framework import serializers
from django.utils import timezone
from django.urls import reverse
from accounts.models import (
    Job,
    JobApplication,
    RecruiterAssessment,
    RecruiterInterview,
    SavedJob,
)


# =====================================================
# JOB SERIALIZER
# =====================================================

class JobSerializer(serializers.ModelSerializer):

    # MongoDB ObjectId must be returned as a string.
    id = serializers.CharField(read_only=True)

    recruiter = serializers.CharField(
        source="recruiter_id",
        read_only=True
    )

    recruiter_name = serializers.CharField(
        source="recruiter.full_name",
        read_only=True
    )

    class Meta:
        model = Job

        fields = [
            "id",
            "recruiter",
            "recruiter_name",
            "title",
            "company_name",
            "company_logo",
            "category",
            "location",
            "job_type",
            "workplace",
            "is_remote",
            "experience_level",
            "salary",
            "salary_min",
            "salary_max",
            "salary_period",
            "application_deadline",
            "description",
            "requirements",
            "skills",
            "status",
            "is_active",
            "applicants_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "recruiter",
            "recruiter_name",
            "is_remote",
            "applicants_count",
            "created_at",
            "updated_at",
        ]


# =====================================================
# SAVED JOB SERIALIZER
# =====================================================

class SavedJobSerializer(serializers.ModelSerializer):

    id = serializers.CharField(read_only=True)

    user = serializers.CharField(
        source="user_id",
        read_only=True
    )

    job = serializers.CharField(
        source="job_id",
        read_only=True
    )

    job_details = JobSerializer(
        source="job",
        read_only=True
    )

    class Meta:
        model = SavedJob

        fields = [
            "id",
            "user",
            "job",
            "job_details",
            "saved_at",
        ]

        read_only_fields = [
            "id",
            "user",
            "job",
            "saved_at",
        ]



class JobApplicationSerializer(serializers.ModelSerializer):

    id = serializers.CharField(read_only=True)

    applicant_name = serializers.CharField(
        source="applicant.full_name",
        read_only=True,
    )
    applicant_email = serializers.EmailField(
        source="applicant.email",
        read_only=True,
    )
    applicant_phone = serializers.CharField(
        source="applicant.phone",
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )
    applicant_location = serializers.CharField(
        source="applicant.location",
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )
    applicant_skills = serializers.JSONField(
        source="applicant.skills",
        read_only=True,
        allow_null=True,
    )

    resume_url = serializers.SerializerMethodField()

    job_id = serializers.CharField(
        source="job.id",
        read_only=True,
    )
    job_title = serializers.CharField(
        source="job.title",
        read_only=True,
    )
    company_name = serializers.CharField(
        source="job.company_name",
        read_only=True,
    )
    location = serializers.CharField(
        source="job.location",
        read_only=True,
    )
    job_type = serializers.CharField(
        source="job.job_type",
        read_only=True,
    )

    class Meta:
        model = JobApplication

        fields = [
            "id",
            "applicant_name",
            "applicant_email",
            "applicant_phone",
            "applicant_location",
            "applicant_skills",
            "resume_url",
            "job_id",
            "job_title",
            "company_name",
            "location",
            "job_type",
            "status",
            "applied_at",
        ]

        read_only_fields = fields

    def get_resume_url(self, application):
        applicant = application.applicant
        resume = getattr(applicant, "resume", None)

        if not resume:
            return ""

        request = self.context.get("request")

        url = (
            f"{reverse('profile-resume')}"
            f"?candidate_id={application.applicant_id}"
        )

        return request.build_absolute_uri(url) if request else url



class RecruiterInterviewSerializer(serializers.ModelSerializer):

    id = serializers.CharField(read_only=True)
    application_id = serializers.CharField(write_only=True)
    application_pk = serializers.CharField(source="application.id", read_only=True)
    candidate_name = serializers.CharField(source="application.applicant.full_name", read_only=True)
    candidate_email = serializers.EmailField(source="application.applicant.email", read_only=True)
    job_title = serializers.CharField(source="application.job.title", read_only=True)
    application = JobApplicationSerializer(read_only=True)

    class Meta:
        model = RecruiterInterview
        fields = [
            "id",
            "application_id",
            "application_pk",
            "application",
            "candidate_name",
            "candidate_email",
            "job_title",
            "scheduled_at",
            "mode",
            "meeting_url",
            "notes",
            "status",
            "score",
            "feedback",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "application",
            "candidate_name",
            "candidate_email",
            "job_title",
            "status",
            "created_at",
        ]

    def validate_application_id(self, value):
        try:
            application = JobApplication.objects.get(pk=value)
        except JobApplication.DoesNotExist as error:
            raise serializers.ValidationError("Application not found.") from error

        request = self.context.get("request")
        if (
            request
            and not request.user.is_staff
            and application.job.recruiter_id != request.user.pk
        ):
            raise serializers.ValidationError("You cannot schedule an interview for this application.")

        return value

    def validate_scheduled_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Interview time must be in the future.")
        return value

    def create(self, validated_data):
        application_id = validated_data.pop("application_id")
        application = JobApplication.objects.get(pk=application_id)
        return RecruiterInterview.objects.create(
            application=application,
            **validated_data
        )


class RecruiterAssessmentSerializer(serializers.ModelSerializer):

    id = serializers.CharField(read_only=True)
    job_id = serializers.CharField(write_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)

    class Meta:
        model = RecruiterAssessment
        fields = [
            "id",
            "job_id",
            "job_title",
            "title",
            "questions",
            "starts_at",
            "duration_minutes",
            "created_at",
        ]
        read_only_fields = ["id", "job_title", "created_at"]

    def validate_questions(self, questions):
        if not isinstance(questions, list) or len(questions) != 10:
            raise serializers.ValidationError("An assessment must contain exactly 10 questions.")

        for index, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                raise serializers.ValidationError(f"Question {index} must be an object.")
            prompt = question.get("question")
            options = question.get("options")
            correct_answer = question.get("correct_answer")
            if (
                not isinstance(prompt, str)
                or not prompt.strip()
                or not isinstance(options, list)
                or len(options) != 4
                or any(not isinstance(option, str) or not option.strip() for option in options)
                or correct_answer not in options
            ):
                raise serializers.ValidationError(
                    f"Question {index} needs a prompt, four options, and a valid correct answer."
                )
        return questions

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and request.user.user_type != "recruiter" and not request.user.is_staff:
            for question in data["questions"]:
                question.pop("correct_answer", None)
        return data

    def validate_starts_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Assessment time must be in the future.")
        return value

    def validate_duration_minutes(self, value):
        if not 1 <= value <= 240:
            raise serializers.ValidationError("Duration must be between 1 and 240 minutes.")
        return value

    def validate_job_id(self, value):
        try:
            job = Job.objects.get(pk=value)
        except Job.DoesNotExist as error:
            raise serializers.ValidationError("Job not found.") from error
        request = self.context.get("request")
        if request and not request.user.is_staff and job.recruiter_id != request.user.pk:
            raise serializers.ValidationError("You cannot create an assessment for this job.")
        return value

    def create(self, validated_data):
        job_id = validated_data.pop("job_id")
        job = Job.objects.get(pk=job_id)
        return RecruiterAssessment.objects.create(job=job, **validated_data)
