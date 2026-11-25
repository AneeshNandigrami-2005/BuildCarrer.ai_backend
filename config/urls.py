
"""
Main URL configuration for BuildCareer.ai
"""

from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # Authentication APIs
    # /auth/register/
    # /auth/login/
    # /auth/google/
    # /auth/profile/
    path("auth/", include("accounts.urls")),

    # Job Management APIs
    # /jobs/
    # /jobs/dashboard/
    # /jobs/applications/
    # /jobs/saved/
    path("jobs/", include("jobs.urls")),
]
