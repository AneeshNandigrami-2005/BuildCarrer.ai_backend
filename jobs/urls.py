
"""
Job Management URLs
BuildCareer.ai
"""

from django.urls import path

from .views import (
    JobListCreateView,
    JobDetailView,
    JobStatusUpdateView,
    SavedJobListCreateView,
    SavedJobDeleteView,
)

from .recruiter_views import (
    JobApplicationDetailView,
    JobApplicationListCreateView,
    JobApplicationWithdrawView,
    RecruiterAssessmentListCreateView,
    RecruiterDashboardSummaryView,
    RecruiterInterviewDetailView,
    RecruiterInterviewListCreateView,
    RecruiterDashboardSummaryView,
)


urlpatterns = [
    # Job APIs
    path("", JobListCreateView.as_view(), name="job-list-create"),

    # Recruiter Dashboard
    path(
        "dashboard/",
        RecruiterDashboardSummaryView.as_view(),
        name="recruiter-dashboard"
    ),

    # Job Applications
    path(
        "applications/",
        JobApplicationListCreateView.as_view(),
        name="job-applications"
    ),

    path(
        "applications/<str:pk>/withdraw/",
        JobApplicationWithdrawView.as_view(),
        name="job-application-withdraw"
    ),

    path(
        "applications/<str:pk>/",
        JobApplicationDetailView.as_view(),
        name="job-application-detail"
    ),

    # Recruiter Interviews
    path(
        "interviews/",
        RecruiterInterviewListCreateView.as_view(),
        name="recruiter-interviews"
    ),

    path(
        "interviews/<str:pk>/",
        RecruiterInterviewDetailView.as_view(),
        name="recruiter-interview-detail"
    ),

    # Recruiter Assessments
    path(
        "assessments/",
        RecruiterAssessmentListCreateView.as_view(),
        name="recruiter-assessments"
    ),

    # Saved Jobs
    path(
        "saved/",
        SavedJobListCreateView.as_view(),
        name="saved-job-list-create"
    ),

    path(
        "saved/<str:pk>/",
        SavedJobDeleteView.as_view(),
        name="saved-job-delete"
    ),

    # Job Status
    path(
        "<str:pk>/status/",
        JobStatusUpdateView.as_view(),
        name="job-status-update"
    ),

    # Job Details
    path(
        "<str:pk>/",
        JobDetailView.as_view(),
        name="job-detail"
    ),
]
