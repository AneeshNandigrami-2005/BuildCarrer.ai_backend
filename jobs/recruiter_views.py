from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import (
    Job,
    JobApplication,
    RecruiterAssessment,
    RecruiterInterview,
)
from .serializers import (
    JobApplicationSerializer,
    RecruiterAssessmentSerializer,
    RecruiterInterviewSerializer,
)


class JobApplicationListCreateView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        recruiter_scope = request.query_params.get("scope") == "recruiter"
        if recruiter_scope and request.user.user_type != "recruiter" and not request.user.is_staff:
            return Response(
                {"detail": "Recruiter access is required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        applications = JobApplication.objects.select_related(
            "applicant",
            "job",
            "job__recruiter",
        )
        if request.user.is_staff:
            pass
        elif request.user.user_type == "recruiter":
            applications = applications.filter(job__recruiter=request.user)
        else:
            applications = applications.filter(applicant=request.user)

        serializer = JobApplicationSerializer(
            applications.order_by("-applied_at"),
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    def post(self, request):
        if request.user.user_type != "job_seeker":
            return Response(
                {"detail": "Only job seekers can apply to jobs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        job = get_object_or_404(
            Job,
            pk=request.data.get("job"),
            status="Active",
            is_active=True,
        )
        application, created = JobApplication.objects.get_or_create(
            applicant=request.user,
            job=job,
        )
        if not created:
            return Response(
                {"detail": "You have already applied for this job."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        job.applicants_count = JobApplication.objects.filter(job=job).count()
        job.save(update_fields=["applicants_count"])

        serializer = JobApplicationSerializer(
            application,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class JobApplicationDetailView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        application = get_object_or_404(
            JobApplication.objects.select_related("job", "applicant"),
            pk=pk,
        )
        if (
            not request.user.is_staff
            and (
                request.user.user_type != "recruiter"
                or application.job.recruiter_id != request.user.pk
            )
        ):
            return Response(
                {"detail": "You cannot update this application."},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_status = request.data.get("status")
        allowed_statuses = {choice[0] for choice in JobApplication.STATUS_CHOICES}
        if new_status not in allowed_statuses:
            return Response(
                {"status": "Choose a valid application status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        application.status = new_status
        application.save(update_fields=["status"])
        serializer = JobApplicationSerializer(
            application,
            context={"request": request},
        )
        return Response(serializer.data)


class JobApplicationWithdrawView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(JobApplication, pk=pk)
        if application.applicant_id != request.user.pk:
            return Response(
                {"detail": "You cannot withdraw another candidate's application."},
                status=status.HTTP_403_FORBIDDEN,
            )
        application.status = "Withdrawn"
        application.save(update_fields=["status"])
        return Response(
            JobApplicationSerializer(
                application,
                context={"request": request},
            ).data,
        )


class RecruiterInterviewListCreateView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        recruiter_scope = request.query_params.get("scope") == "recruiter"

        if (
            not request.user.is_staff
            and request.user.user_type not in ["recruiter", "job_seeker"]
        ):
            return Response(
                {"detail": "You do not have permission to view interviews."},
                status=status.HTTP_403_FORBIDDEN,
            )

        interviews = RecruiterInterview.objects.select_related(
            "application",
            "application__applicant",
            "application__job",
            "recruiter",
        )
        if request.user.is_staff:
            pass
        elif request.user.user_type == "recruiter":
            interviews = interviews.filter(recruiter=request.user)
        else:
            interviews = interviews.filter(application__applicant=request.user)

        serializer = RecruiterInterviewSerializer(
            interviews.order_by("scheduled_at"),
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    def post(self, request):
        if request.user.user_type != "recruiter":
            return Response(
                {"detail": "Only recruiters can schedule interviews."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = RecruiterInterviewSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        interview = serializer.save(recruiter=request.user)
        if interview.application.status == "Applied":
            interview.application.status = "CV Selected"
            interview.application.save(update_fields=["status"])
        return Response(
            RecruiterInterviewSerializer(
                interview,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class RecruiterInterviewDetailView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        interview = get_object_or_404(
            RecruiterInterview.objects.select_related("application", "recruiter"),
            pk=pk,
        )
        if (
            not request.user.is_staff
            and (
                request.user.user_type != "recruiter"
                or interview.recruiter_id != request.user.pk
            )
        ):
            return Response(
                {"detail": "You cannot update this interview."},
                status=status.HTTP_403_FORBIDDEN,
            )

        allowed_fields = {"status", "score", "feedback"}
        if set(request.data) - allowed_fields:
            return Response(
                {"detail": "Only status, score, and feedback can be updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "status" in request.data:
            valid_statuses = {choice[0] for choice in RecruiterInterview.STATUS_CHOICES}
            if request.data["status"] not in valid_statuses:
                return Response(
                    {"status": "Choose a valid interview status."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            interview.status = request.data["status"]

        if "score" in request.data:
            score = request.data["score"]
            if score is not None and (
                type(score) is not int or not 0 <= score <= 100
            ):
                return Response(
                    {"score": "Score must be an integer between 0 and 100."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            interview.score = score

        if "feedback" in request.data:
            interview.feedback = request.data["feedback"]

        interview.save()
        return Response(
            RecruiterInterviewSerializer(
                interview,
                context={"request": request},
            ).data,
        )


class RecruiterAssessmentListCreateView(generics.ListCreateAPIView):

    serializer_class = RecruiterAssessmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        assessments = RecruiterAssessment.objects.select_related("job", "recruiter")
        if user.is_staff:
            return assessments.order_by("-starts_at")
        if user.user_type == "recruiter":
            return assessments.filter(recruiter=user).order_by("-starts_at")
        return assessments.filter(
            job__applications__applicant=user
        ).distinct().order_by("-starts_at")

    def perform_create(self, serializer):
        if self.request.user.user_type != "recruiter":
            raise PermissionDenied("Only recruiters can create assessments.")
        serializer.save(recruiter=self.request.user)


class RecruiterDashboardSummaryView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.user_type != "recruiter" and not request.user.is_staff:
            return Response(
                {"detail": "Recruiter access is required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        jobs = Job.objects.filter(recruiter=request.user)
        applications = JobApplication.objects.filter(job__recruiter=request.user)
        interviews = RecruiterInterview.objects.filter(recruiter=request.user)
        return Response({
            "jobs": jobs.count(),
            "active_jobs": jobs.filter(status="Active", is_active=True).count(),
            "applications": applications.count(),
            "interviews": interviews.count(),
            "upcoming_interviews": interviews.filter(
                status="Scheduled",
                scheduled_at__gte=timezone.now(),
            ).count(),
            "selected": applications.filter(status="Selected").count(),
            "cv_selected": applications.filter(status="CV Selected").count(),
            "qualified": applications.filter(
                status__in=["1st Round Qualified", "2nd Round Qualified"]
            ).count(),
            "recent_applications": JobApplicationSerializer(
                applications.select_related("applicant", "job").order_by("-applied_at")[:5],
                many=True,
                context={"request": request},
            ).data,
            "upcoming": RecruiterInterviewSerializer(
                interviews.select_related(
                    "application",
                    "application__applicant",
                    "application__job",
                ).filter(
                    status="Scheduled",
                    scheduled_at__gte=timezone.now(),
                ).order_by("scheduled_at")[:5],
                many=True,
                context={"request": request},
            ).data,
        })
