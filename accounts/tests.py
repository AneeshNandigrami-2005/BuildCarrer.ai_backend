from django.test import TestCase

from .serializers import RegisterSerializer


class RegisterSerializerTests(TestCase):
    def test_create_persists_separate_first_and_last_names(self):
        serializer = RegisterSerializer(
            data={
                "user_type": "job_seeker",
                "first_name": "Avery",
                "last_name": "Jordan",
                "email": "avery.jordan@example.com",
                "phone": "5551234567",
                "date_of_birth": "2000-01-15",
                "password": "secure-password",
                "confirm_password": "secure-password",
                "terms_accepted": True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        user.refresh_from_db()

        self.assertEqual(user.first_name, "Avery")
        self.assertEqual(user.last_name, "Jordan")
        self.assertEqual(user.full_name, "Avery Jordan")
