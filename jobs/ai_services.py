import json
import re

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

from accounts.models import Job, SavedJob


def _is_greeting(prompt):
    return bool(
        re.fullmatch(
            r"(?:hi+|hello+|hey+|good\s+(?:morning|afternoon|evening))[!,.?\s]*",
            prompt.strip(),
            flags=re.IGNORECASE,
        )
    )


def _extract_direct_job_criteria(prompt):
    original_text = prompt.strip()
    text = original_text.lower()
    job_type = ""
    if re.search(r"\bpart[\s-]?time\b", text):
        job_type = "Part-time"
    elif re.search(r"\bfull[\s-]?time\b", text):
        job_type = "Full-time"
    elif re.search(r"\bintern(?:ship)?\b", text):
        job_type = "Internship"

    experience_level = ""
    if re.search(r"\b(?:fresher|entry[\s-]?level|new graduate)\b", text):
        experience_level = "Fresher"

    location = ""
    location_match = re.search(
        r"\b(?:in|near|around)\s+([a-z][a-z .'-]*?)(?=,|"
        r"\bwith\b|\bfor\b|\bpart[\s-]?time\b|\bfull[\s-]?time\b|"
        r"\binternship\b|\bfresher\b|\bsalary\b|\bexpected\b|$)",
        original_text,
        flags=re.IGNORECASE,
    )
    if location_match:
        location = location_match.group(1).strip(" .,-")
        text = text[: location_match.start()] + " " + text[location_match.end() :]
    elif re.search(r"\bremote\b", text):
        location = "Remote"

    min_salary = None
    max_salary = None
    salary_period = ""
    salary_range = re.search(
        r"\b(?:between|from)?\s*(\d+(?:\.\d+)?)\s*(?:-|to|and)\s*"
        r"(\d+(?:\.\d+)?)\s*(lpa|lakhs?)\b",
        text,
    )
    if salary_range:
        min_salary = float(salary_range.group(1)) * 100000
        max_salary = float(salary_range.group(2)) * 100000
        salary_period = "year"
    else:
        salary = re.search(r"(\d+(?:\.\d+)?)\s*(lpa|lakhs?)\b", text)
        if salary:
            amount = float(salary.group(1)) * 100000
            if re.search(r"\b(?:under|below|up to|upto)\b", text):
                max_salary = amount
            else:
                min_salary = amount
            salary_period = "year"

    keyword_text = re.sub(
        r"\b(?:\d+(?:\.\d+)?\s*(?:lpa|lakhs?)|"
        r"please|can|could|you|find|search|show|list|look|looking|"
        r"want|need|am|i|me|some|any|those|a|an|the|job|jobs|"
        r"vacancy|vacancies|opening|openings|position|positions|role|roles|"
        r"in|near|around|with|for|expected|expectation|salary|pay|paying|"
        r"offering|remote|full[\s-]?time|part[\s-]?time|internship|intern|"
        r"fresher|entry[\s-]?level|new graduate|experience)\b",
        " ",
        text,
    )
    keywords = re.sub(r"[^a-z0-9+#.]+", " ", keyword_text)
    keywords = " ".join(keywords.split()).strip(" .")

    has_job_intent = bool(
        re.search(r"\b(?:jobs?|vacancies|openings?|positions?|roles?)\b", prompt, re.I)
        or re.search(
            r"\b(?:developer|engineer|designer|analyst|intern|accountant|"
            r"manager|tester|architect|consultant|teacher|nurse|"
            r"frontend|front-end|backend|back-end|full stack|software|"
            r"data scientist|product manager)\b",
            prompt,
            re.I,
        )
        or job_type
        or experience_level
        or min_salary is not None
        or max_salary is not None
    )
    if not has_job_intent:
        return None

    criteria = {
        "keywords": keywords,
        "location": location,
        "min_salary": min_salary,
        "max_salary": max_salary,
        "salary_period": salary_period,
        "job_type": job_type,
        "experience_level": experience_level,
    }
    return criteria if any(criteria.values()) else None


def _format_job_search_reply(result):
    if result["status"] != "found":
        return "I couldn't find active jobs matching those criteria. Try another title, location, or salary range."

    reply = f"I found {result['total_matches']} matching active job(s)."
    if result["saved"]:
        reply += " Added to Saved Jobs: " + ", ".join(result["saved"]) + "."
    if result["already_saved"]:
        reply += " Already in Saved Jobs: " + ", ".join(result["already_saved"]) + "."
    return reply


def _search_and_save_jobs(
    user,
    *,
    keywords="",
    location="",
    min_salary=None,
    max_salary=None,
    salary_period="",
    job_type="",
    experience_level="",
):
    if not any((
        keywords,
        location,
        min_salary is not None,
        max_salary is not None,
        job_type,
        experience_level,
    )):
        return {
            "status": "needs_criteria",
            "message": "Specify a job title, location, job type, experience level, or salary range to search.",
            "jobs": [],
        }

    queryset = Job.objects.filter(status="Active", is_active=True)

    if keywords:
        queryset = queryset.filter(
            Q(title__icontains=keywords)
            | Q(company_name__icontains=keywords)
            | Q(category__icontains=keywords)
            | Q(description__icontains=keywords)
            | Q(requirements__icontains=keywords)
        )

    if location:
        if location.strip().lower() == "remote":
            queryset = queryset.filter(
                Q(location__icontains=location)
                | Q(workplace__iexact="Remote")
                | Q(is_remote=True)
            )
        else:
            queryset = queryset.filter(location__icontains=location)

    if job_type:
        normalized_type = job_type.strip().lower().replace("_", "-")
        job_type_aliases = {
            "full time": "Full-time",
            "full-time": "Full-time",
            "part time": "Part-time",
            "part-time": "Part-time",
            "intern": "Internship",
            "internship": "Internship",
        }
        queryset = queryset.filter(
            job_type__iexact=job_type_aliases.get(normalized_type, job_type.strip())
        )

    if experience_level:
        normalized_experience = experience_level.strip().lower()
        if normalized_experience in {"fresher", "entry-level", "entry level"}:
            queryset = queryset.filter(
                Q(experience_level__icontains="fresher")
                | Q(experience_level__icontains="entry")
                | Q(experience_level__icontains="0 year")
                | Q(experience_level__icontains="no experience")
            )
        else:
            queryset = queryset.filter(
                experience_level__icontains=experience_level.strip()
            )

    if min_salary is not None or max_salary is not None:
        if salary_period:
            queryset = queryset.filter(salary_period__iexact=salary_period)
        if min_salary is not None:
            queryset = queryset.filter(salary_max__gte=min_salary)
        if max_salary is not None:
            queryset = queryset.filter(salary_min__lte=max_salary)

    total_matches = queryset.count()
    jobs = queryset.order_by("-created_at")[:10]
    saved_jobs = []
    already_saved = []
    serialized_jobs = []

    for job in jobs:
        _, created = SavedJob.objects.get_or_create(user=user, job=job)
        (saved_jobs if created else already_saved).append(job.title)
        serialized_jobs.append(
            {
                "id": str(job.pk),
                "title": job.title,
                "company": job.company_name,
                "location": job.location,
                "job_type": job.job_type,
                "salary": job.salary,
                "salary_min": str(job.salary_min) if job.salary_min is not None else None,
                "salary_max": str(job.salary_max) if job.salary_max is not None else None,
                "salary_period": job.salary_period,
                "skills": job.skills,
            }
        )

    return {
        "status": "found" if serialized_jobs else "no_results",
        "total_matches": total_matches,
        "saved": saved_jobs,
        "already_saved": already_saved,
        "jobs": serialized_jobs,
    }


def get_ai_job_recommendation(user_prompt, chat_history=None, user=None):
    if user is None or not user.is_authenticated:
        raise ValueError("Authenticated user is required.")

    if _is_greeting(user_prompt):
        return {
            "reply": (
                "Hello! I am your personal AI Career Assistant at BuildCareer.ai. "
                "How can I help you today?"
            ),
            "job_search": None,
        }

    direct_criteria = _extract_direct_job_criteria(user_prompt)
    if direct_criteria:
        result = _search_and_save_jobs(user, **direct_criteria)
        return {
            "reply": _format_job_search_reply(result),
            "job_search": result,
        }

    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key:
        raise ImproperlyConfigured(
            "Set GEMINI_API_KEY in the backend environment to enable the AI assistant."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as error:
        raise ImproperlyConfigured(
            "The google-genai package is required for the AI assistant."
        ) from error

    search_results = []

    def search_jobs(
        keywords: str = "",
        location: str = "",
        min_salary: float = None,
        max_salary: float = None,
        salary_period: str = "",
        job_type: str = "",
        experience_level: str = "",
    ) -> str:
        """Find and save active jobs by title, location, salary, job type, or experience."""
        result = _search_and_save_jobs(
            user,
            keywords=keywords.strip(),
            location=location.strip(),
            min_salary=min_salary,
            max_salary=max_salary,
            salary_period=salary_period.strip(),
            job_type=job_type.strip(),
            experience_level=experience_level.strip(),
        )
        search_results.append(result)
        return json.dumps(result)

    system_instruction = """
    You are BuildCareer.ai, an intelligent AI career assistant.
    Search only the real active jobs returned by search_jobs; never invent jobs or IDs.
    When the user asks to find jobs or gives a job title, location, salary range,
    employment type (including part-time and internships), or experience level
    (including fresher), call search_jobs using all relevant details from the current
    request and recent conversation. Search results are automatically saved to this
    user's Saved Jobs dashboard. Tell the user which
    jobs were newly saved and which were already saved; never claim a save not confirmed
    by the tool. If no jobs match, say so and do not invent alternatives.
    Salary values use the job posting's currency units and salary_period. For Indian
    annual salaries stated in LPA, convert 1 LPA to 100000 INR before calling the tool.
    Ask for search criteria instead of searching without a title, location, or salary.
    Be friendly, professional, and concise.
    """

    history_lines = []
    for item in (chat_history or [])[-10:]:
        role = item.get("role")
        text = item.get("text")
        if role in {"user", "assistant"} and isinstance(text, str) and text.strip():
            label = "User" if role == "user" else "Assistant"
            history_lines.append(f"{label}: {text.strip()[:2000]}")

    prompt = user_prompt.strip()
    if history_lines:
        prompt = (
            "Recent conversation context:\n"
            + "\n".join(history_lines)
            + "\n\nCurrent user message:\n"
            + prompt
        )

    client = genai.Client(api_key=api_key)
    chat = client.chats.create(
        model=settings.GEMINI_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[search_jobs],
            temperature=0.3,
        ),
    )
    response = chat.send_message(prompt)
    reply = response.text
    if not reply and search_results:
        result = search_results[-1]
        if result["status"] == "found":
            saved_count = len(result["saved"])
            reply = (
                f"I found {result['total_matches']} matching active job(s). "
                f"{saved_count} new job(s) were added to your Saved Jobs."
            )
            if result["saved"]:
                reply += " Newly saved: " + ", ".join(result["saved"]) + "."
            if result["already_saved"]:
                reply += " Already saved: " + ", ".join(result["already_saved"]) + "."
        else:
            reply = "I couldn't find active jobs matching those criteria."
    return {
        "reply": reply or "I couldn't generate a response. Please try again.",
        "job_search": search_results[-1] if search_results else None,
    }
