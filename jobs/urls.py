
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
)

urlpatterns = [
    # Job APIs
    path("", JobListCreateView.as_view(), name="job-list-create"),
    path("dashboard/", RecruiterDashboardSummaryView.as_view(), name="recruiter-dashboard"),
    path("applications/", JobApplicationListCreateView.as_view(), name="job-applications"),
    path("applications/<str:pk>/withdraw/", JobApplicationWithdrawView.as_view(), name="job-application-withdraw"),
    path("applications/<str:pk>/", JobApplicationDetailView.as_view(), name="job-application-detail"),
    path("interviews/", RecruiterInterviewListCreateView.as_view(), name="recruiter-interviews"),
    path("interviews/<str:pk>/", RecruiterInterviewDetailView.as_view(), name="recruiter-interview-detail"),
    path("assessments/", RecruiterAssessmentListCreateView.as_view(), name="recruiter-assessments"),

    # Saved Job APIs - keep these before the generic job detail route
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

    # Job status and detail APIs
    path(
        "<str:pk>/status/",
        JobStatusUpdateView.as_view(),
        name="job-status-update"
    ),

    path(
        "<str:pk>/",
        JobDetailView.as_view(),
        name="job-detail"
    ),
]
