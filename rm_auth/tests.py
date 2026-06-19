from django.test import Client, TestCase
from django.urls import reverse

from django.contrib.auth.models import User

from .models import RMUser


class RMAuthTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@test.com",
            password="adminpass123",
        )
        self.rm = RMUser.objects.create(
            user_id="rm_test",
            email="rm@test.com",
            created_by=self.admin,
        )
        self.rm.set_password("oldpass123")
        self.rm.save()
        self.client = Client()

    def test_login_success(self):
        response = self.client.post(
            reverse("rm_auth:login"),
            {"user_id": "rm_test", "password": "oldpass123"},
        )
        self.assertRedirects(response, reverse("rm_auth:dashboard"))
        self.assertEqual(self.client.session.get("rm_user_id"), self.rm.pk)

    def test_login_invalid_password(self):
        response = self.client.post(
            reverse("rm_auth:login"),
            {"user_id": "rm_test", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("rm_user_id", self.client.session)

    def test_change_password(self):
        self.client.post(
            reverse("rm_auth:login"),
            {"user_id": "rm_test", "password": "oldpass123"},
        )
        response = self.client.post(
            reverse("rm_auth:change_password"),
            {
                "user_id": "rm_test",
                "old_password": "oldpass123",
                "email": "rm@test.com",
                "new_password": "newpass456",
                "confirm_password": "newpass456",
            },
        )
        self.assertRedirects(response, reverse("rm_auth:dashboard"))
        self.rm.refresh_from_db()
        self.assertTrue(self.rm.check_password("newpass456"))

    def test_logout(self):
        self.client.post(
            reverse("rm_auth:login"),
            {"user_id": "rm_test", "password": "oldpass123"},
        )
        response = self.client.post(reverse("rm_auth:logout"))
        self.assertRedirects(response, reverse("rm_auth:login"))
        self.assertNotIn("rm_user_id", self.client.session)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("rm_auth:dashboard"))
        self.assertRedirects(response, "/auth/login/")
