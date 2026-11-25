
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import (
    Job,
    JobApplication,
    RecruiterAssessment,
    RecruiterInterview,
    SavedJob,
)
from .serializers import (
    JobApplicationSerializer,
    JobSerializer,
    RecruiterAssessmentSerializer,
    RecruiterInterviewSerializer,
    SavedJobSerializer,
)


# =====================================================
# PERMISSIONS
# =====================================================

class CanCreateJob(permissions.BasePermission):

    def has_permission(self, request, view):

        if not request.user or not request.user.is_authenticated:
            return False

        return (
            request.user.is_staff
            or request.user.user_type == "recruiter"
        )


class IsAdminOrOwnerRecruiter(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        # Anyone can read an object if the view queryset permits it.
        if request.method in permissions.SAFE_METHODS:
            return True

        if request.user.is_staff:
            return True

        return (
            request.user.user_type == "recruiter"
            and obj.recruiter_id == request.user.pk
        )


# =====================================================
# JOB LIST AND CREATE
# =====================================================

class JobListCreateView(generics.ListCreateAPIView):

    serializer_class = JobSerializer
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly
    ]

    def get_queryset(self):

        user = self.request.user

        if user.is_authenticated:

            # Admin can see all jobs.
            if user.is_staff:
                return Job.objects.all().order_by("-created_at")

            # Recruiters can see their own jobs.
            if user.user_type == "recruiter":
                return Job.objects.filter(
                    recruiter=user
                ).order_by("-created_at")

        # Job seekers and anonymous visitors see active jobs.
        return Job.objects.filter(
            status="Active",
            is_active=True
        ).order_by("-created_at")

    def get_permissions(self):

        if self.request.method == "POST":
            return [CanCreateJob()]

        return super().get_permissions()

    def perform_create(self, serializer):

        serializer.save(
            recruiter=self.request.user,
            is_active=True
        )


# =====================================================
# JOB DETAIL, UPDATE AND DELETE
# =====================================================

class JobDetailView(generics.RetrieveUpdateDestroyAPIView):

    serializer_class = JobSerializer

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
        IsAdminOrOwnerRecruiter
    ]

    lookup_field = "pk"

    def get_queryset(self):

        user = self.request.user

        if user.is_authenticated:

            if user.is_staff:
                return Job.objects.all()

            if user.user_type == "recruiter":
                return Job.objects.filter(recruiter=user)

        return Job.objects.filter(
            status="Active",
            is_active=True
        )

    def perform_update(self, serializer):

        job = serializer.save()

        job.is_active = job.status == "Active"
        job.save()

    def perform_destroy(self, instance):

        instance.delete()


# =====================================================
# UPDATE JOB STATUS
# =====================================================

class JobStatusUpdateView(APIView):

    permission_classes = [
        permissions.IsAuthenticated
    ]

    def patch(self, request, pk):

        job = get_object_or_404(Job, pk=pk)

        # Admin or owning recruiter only.
        if not request.user.is_staff:

            if (
                request.user.user_type != "recruiter"
                or job.recruiter_id != request.user.pk
            ):
                return Response(
                    {"error": "You cannot change this job status."},
                    status=status.HTTP_403_FORBIDDEN
                )

        new_status = request.data.get("status")

        allowed_statuses = [
            "Active",
            "Inactive",
            "Closed"
        ]

        if new_status not in allowed_statuses:
            return Response(
                {"error": "Invalid job status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        job.status = new_status
        job.is_active = new_status == "Active"
        job.save()

        return Response(
            {
                "message": "Job status updated successfully.",
                "status": job.status,
                "is_active": job.is_active
            },
            status=status.HTTP_200_OK
        )


# =====================================================
# SAVED JOB LIST AND CREATE
# =====================================================

class SavedJobListCreateView(generics.ListCreateAPIView):

    serializer_class = SavedJobSerializer
    permission_classes = [
        permissions.IsAuthenticated
    ]

    def get_queryset(self):

        return SavedJob.objects.filter(
            user=self.request.user
        ).order_by("-saved_at")

    def create(self, request, *args, **kwargs):

        job_id = request.data.get("job")

        if not job_id:
            return Response(
                {"error": "Job ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        job = get_object_or_404(
            Job,
            pk=job_id,
            status="Active",
            is_active=True
        )

        saved_job, created = SavedJob.objects.get_or_create(
            user=request.user,
            job=job
        )

        serializer = self.get_serializer(saved_job)

        return Response(
            {
                "message": (
                    "Job saved successfully."
                    if created
                    else "Job is already saved."
                ),
                "saved_job": serializer.data
            },
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            )
        )


# =====================================================
# REMOVE SAVED JOB
# =====================================================

class SavedJobDeleteView(APIView):

    permission_classes = [
        permissions.IsAuthenticated
    ]

    def delete(self, request, pk):

        saved_job = get_object_or_404(
            SavedJob,
            pk=pk,
            user=request.user
        )

        saved_job.delete()

        return Response(
            {"message": "Saved job removed successfully."},
            status=status.HTTP_200_OK
        )
