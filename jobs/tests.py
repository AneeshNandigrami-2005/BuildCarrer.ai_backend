from django.test import TestCase

# Create your tests here.
from types import SimpleNamespace
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError

from accounts.models import Job, JobApplication
from .ai_services import _search_and_save_jobs
from .ai_services import get_ai_job_recommendation
from .serializers import RecruiterAssessmentSerializer


class RecruiterAssessmentQuestionTests(SimpleTestCase):

    def test_assessment_requires_exactly_ten_questions(self):
        serializer = RecruiterAssessmentSerializer()
        questions = [
            {
                "question": f"Question {index}",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            }
            for index in range(10)
        ]

        self.assertEqual(serializer.validate_questions(questions), questions)

        with self.assertRaises(ValidationError):
            serializer.validate_questions(questions[:9])

    def test_question_requires_four_options_and_a_valid_answer(self):
        serializer = RecruiterAssessmentSerializer()
        question = [{
            "question": "Choose the correct answer",
            "options": ["A", "B", "C"],
            "correct_answer": "D",
        } for _ in range(10)]

        with self.assertRaises(ValidationError):
            serializer.validate_questions(question)


class AIJobSearchTests(SimpleTestCase):

    @override_settings(GEMINI_API_KEY="")
    def test_greeting_is_answered_without_ai_configuration(self):
        result = get_ai_job_recommendation(
            "Hii",
            user=SimpleNamespace(is_authenticated=True),
        )

        self.assertEqual(
            result["reply"],
            "Hello! I am your personal AI Career Assistant at BuildCareer.ai. How can I help you today?",
        )
        self.assertIsNone(result["job_search"])

    @patch("jobs.ai_services._search_and_save_jobs")
    def test_job_search_uses_local_filters_without_calling_the_ai_provider(
        self,
        search_jobs,
    ):
        search_jobs.return_value = {
            "status": "found",
            "total_matches": 1,
            "saved": ["Frontend Developer"],
            "already_saved": [],
            "jobs": [
                {
                    "title": "Frontend Developer",
                    "company": "BuildCareer",
                    "location": "Pune",
                    "job_type": "Part-time",
                    "salary": "",
                }
            ],
        }

        result = get_ai_job_recommendation(
            "Find frontend developer jobs in Pune, part-time for fresher, salary expectation 8 LPA",
            user=SimpleNamespace(is_authenticated=True),
        )

        self.assertEqual(result["job_search"]["saved"], ["Frontend Developer"])
        self.assertIn("Frontend Developer", result["reply"])
        search_jobs.assert_called_once_with(
            SimpleNamespace(is_authenticated=True),
            keywords="frontend developer",
            location="Pune",
            min_salary=800000,
            max_salary=None,
            salary_period="year",
            job_type="Part-time",
            experience_level="Fresher",
        )

    @patch("jobs.ai_services.SavedJob.objects.get_or_create")
    @patch("jobs.ai_services.Job.objects.filter")
    def test_search_saves_matching_jobs_and_reports_results(
        self,
        filter_jobs,
        get_or_create_saved_job,
    ):
        job = SimpleNamespace(
            pk="job-id",
            title="Backend Developer",
            company_name="BuildCareer",
            location="Remote",
            job_type="Full-time",
            salary="",
            salary_min=50000,
            salary_max=80000,
            salary_period="month",
            skills=["Python"],
        )
        queryset = filter_jobs.return_value
        queryset.filter.return_value = queryset
        queryset.count.return_value = 1
        queryset.order_by.return_value = [job]
        get_or_create_saved_job.return_value = (None, True)
        user = SimpleNamespace(is_authenticated=True)

        result = _search_and_save_jobs(
            user,
            keywords="Backend Developer",
            location="Remote",
            min_salary=50000,
            max_salary=80000,
            salary_period="month",
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["saved"], ["Backend Developer"])
        self.assertEqual(result["jobs"][0]["id"], "job-id")
        get_or_create_saved_job.assert_called_once_with(user=user, job=job)
        filter_kwargs = [
            call.kwargs for call in queryset.filter.call_args_list
        ]
        self.assertIn({"salary_period__iexact": "month"}, filter_kwargs)

    @patch("jobs.ai_services.Job.objects.filter")
    def test_search_filters_by_job_type_and_fresher_experience(self, filter_jobs):
        queryset = filter_jobs.return_value
        queryset.filter.return_value = queryset
        queryset.count.return_value = 0
        queryset.order_by.return_value = []

        result = _search_and_save_jobs(
            SimpleNamespace(),
            job_type="part time",
            experience_level="Fresher",
        )

        self.assertEqual(result["status"], "no_results")
        filter_kwargs = [call.kwargs for call in queryset.filter.call_args_list]
        self.assertIn({"job_type__iexact": "Part-time"}, filter_kwargs)
        self.assertTrue(
            any(call.args for call in queryset.filter.call_args_list),
            "Fresher search should include experience-level alternatives.",
        )

    @patch("jobs.ai_services.Job.objects.filter")
    def test_search_requires_at_least_one_job_criterion(self, filter_jobs):
        result = _search_and_save_jobs(SimpleNamespace(),)

        self.assertEqual(result["status"], "needs_criteria")
        filter_jobs.assert_not_called()

    @override_settings(GEMINI_API_KEY="test-key", GEMINI_MODEL="gemini-test")
    @patch("google.genai.Client")
    def test_chat_uses_recent_history_and_configured_model(self, client_class):
        client = client_class.return_value
        client.chats.create.return_value.send_message.return_value.text = "Found jobs."

        result = get_ai_job_recommendation(
            "Show me those jobs",
            chat_history=[{"role": "user", "text": "Find remote Python roles"}],
            user=SimpleNamespace(is_authenticated=True),
        )

        self.assertEqual(result["reply"], "Found jobs.")
        self.assertIsNone(result["job_search"])
        client.chats.create.assert_called_once()
        call = client.chats.create.call_args
        self.assertEqual(call.kwargs["model"], "gemini-test")
        prompt = client.chats.create.return_value.send_message.call_args.args[0]
        self.assertIn("Find remote Python roles", prompt)
        self.assertIn("Show me those jobs", prompt)


class RecruiterWorkflowApiTests(TestCase):

    def setUp(self):
        user_model = get_user_model()
        self.recruiter = user_model.objects.create_user(
            email="recruiter@example.com",
            password="secure-password",
            full_name="Riley Recruiter",
            phone="5551234567",
            user_type="recruiter",
        )
        self.candidate = user_model.objects.create_user(
            email="candidate@example.com",
            password="secure-password",
            full_name="Casey Candidate",
            phone="5559876543",
            user_type="job_seeker",
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title="Frontend Developer",
            company_name="BuildCareer",
            location="Remote",
            description="Build frontend features.",
        )
        self.application = JobApplication.objects.create(
            applicant=self.candidate,
            job=self.job,
        )
        self.client = APIClient()

    def test_recruiter_can_only_list_applications_for_owned_jobs(self):
        self.client.force_authenticate(self.recruiter)

        response = self.client.get("/api/jobs/applications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["applicant_email"], self.candidate.email)

    def test_candidate_cannot_request_recruiter_application_scope(self):
        self.client.force_authenticate(self.candidate)

        response = self.client.get("/api/jobs/applications/?scope=recruiter")

        self.assertEqual(response.status_code, 403)

    @patch(
        "accounts.views.get_ai_job_recommendation",
        return_value={
            "reply": "I found one Frontend Developer role.",
            "job_search": {"status": "found", "saved": ["Frontend Developer"]},
        },
    )
    def test_chat_endpoint_returns_saved_job_results(self, get_recommendation):
        self.client.force_authenticate(self.candidate)

        response = self.client.post(
            "/api/auth/ai-job-chat/",
            {"message": "Find frontend developer jobs"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reply"], "I found one Frontend Developer role.")
        self.assertEqual(
            response.data["job_search"]["saved"],
            ["Frontend Developer"],
        )
        get_recommendation.assert_called_once()

    def test_only_applicant_or_their_recruiter_can_view_resume(self):
        self.candidate.resume = "resumes/candidate.pdf"
        self.candidate.save(update_fields=["resume"])
        resume_url = f"/api/auth/profile/resume/?candidate_id={self.candidate.id}"
        self.client.force_authenticate(self.recruiter)

        with patch("django.db.models.fields.files.FieldFile.open", return_value=BytesIO(b"resume")):
            response = self.client.get(resume_url)

        self.assertEqual(response.status_code, 200)

        other_recruiter = get_user_model().objects.create_user(
            email="other@example.com",
            password="secure-password",
            full_name="Other Recruiter",
            phone="5550000000",
            user_type="recruiter",
        )
        self.client.force_authenticate(other_recruiter)

        response = self.client.get(resume_url)

        self.assertEqual(response.status_code, 403)

    def test_recruiter_can_schedule_interview_for_job_applicant(self):
        self.client.force_authenticate(self.recruiter)
        scheduled_at = (timezone.now() + timedelta(days=1)).isoformat()

        response = self.client.post(
            "/api/jobs/interviews/",
            {
                "application_id": str(self.application.id),
                "scheduled_at": scheduled_at,
                "mode": "Video",
                "meeting_url": "https://meet.example.com/interview",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["candidate_name"], self.candidate.full_name)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "CV Selected")

    def test_candidate_can_withdraw_only_their_own_application(self):
        self.client.force_authenticate(self.candidate)

        response = self.client.post(
            f"/api/jobs/applications/{self.application.id}/withdraw/"
        )

        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "Withdrawn")

    def test_recruiter_cannot_withdraw_a_candidate_application(self):
        self.client.force_authenticate(self.recruiter)

        response = self.client.post(
            f"/api/jobs/applications/{self.application.id}/withdraw/"
        )

        self.assertEqual(response.status_code, 403)

    def test_candidate_assessments_do_not_expose_correct_answers(self):
        from accounts.models import RecruiterAssessment

        assessment = RecruiterAssessment.objects.create(
            recruiter=self.recruiter,
            job=self.job,
            title="Frontend basics",
            starts_at=timezone.now() + timedelta(days=1),
            duration_minutes=30,
            questions=[
                {
                    "question": f"Question {index}",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                }
                for index in range(10)
            ],
        )
        self.client.force_authenticate(self.candidate)

        response = self.client.get("/api/jobs/assessments/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], str(assessment.id))
        self.assertNotIn("correct_answer", response.data[0]["questions"][0])
