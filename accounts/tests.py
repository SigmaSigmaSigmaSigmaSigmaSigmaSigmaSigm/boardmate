from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class AccountsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.data = {
            "username": "marta",
            "email": "marta@example.com",
            "password": "Forest-Game-482!",
            "password_confirmation": "Forest-Game-482!",
        }

    def register(self, **changes):
        return self.client.post(
            "/api/auth/register/", self.data | changes, format="json"
        )

    def test_registration_hashes_password_and_optional_names(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["first_name"], "")
        self.assertFalse(response.data["is_staff"])
        self.assertNotIn("password", response.data)
        user = User.objects.get(username="marta")
        self.assertNotEqual(user.password, self.data["password"])
        self.assertTrue(user.check_password(self.data["password"]))
        self.assertEqual(self.register().status_code, 400)
        self.assertEqual(
            self.register(
                username="other", first_name="Марта", last_name="Лісова"
            ).status_code,
            201,
        )

    def test_field_errors_and_maximum_lengths(self):
        response = self.client.post("/api/auth/register/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            set(response.data["errors"]),
            {"username", "email", "password", "password_confirmation"},
        )
        for field, value in [
            ("username", "x" * 151),
            ("first_name", "x" * 151),
            ("last_name", "x" * 151),
            ("email", "x" * 255 + "@example.com"),
            ("email", "invalid"),
            ("password", "short"),
            ("password", "x" * 129),
            ("password_confirmation", "x" * 129),
            ("password_confirmation", "different"),
            ("username", ""),
            ("email", ""),
            ("password", ""),
            ("password_confirmation", ""),
        ]:
            with self.subTest(field=field, value=value[:10]):
                response = self.register(**{field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data["errors"])
        self.assertEqual(User.objects.count(), 0)

    def test_password_strength_and_privilege_injection(self):
        for password in ["password", "123456789", "marta123"]:
            self.assertEqual(
                self.register(
                    password=password, password_confirmation=password
                ).status_code,
                400,
            )
        response = self.register(is_staff=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_login_me_refresh_and_expired_access(self):
        self.register()
        response = self.client.post(
            "/api/auth/login/",
            {"username": "marta", "password": self.data["password"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"access", "refresh"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        me = self.client.get("/api/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["email"], "marta@example.com")
        expired = RefreshToken.for_user(User.objects.get(username="marta")).access_token
        expired.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired}")
        self.assertEqual(self.client.get("/api/me/").status_code, 401)
        refreshed = self.client.post(
            "/api/auth/refresh/", {"refresh": response.data["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.data['access']}")
        self.assertEqual(self.client.get("/api/me/").status_code, 200)

    def test_bad_login_invalid_refresh_and_inactive_user(self):
        self.register()
        self.assertEqual(
            self.client.post(
                "/api/auth/login/",
                {"username": "marta", "password": "wrong"},
                format="json",
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/refresh/", {"refresh": "invalid"}, format="json"
            ).status_code,
            401,
        )
        refresh = RefreshToken.for_user(User.objects.get(username="marta"))
        refresh.set_exp(lifetime=timedelta(seconds=-1))
        self.assertEqual(
            self.client.post(
                "/api/auth/refresh/", {"refresh": str(refresh)}, format="json"
            ).status_code,
            401,
        )
        user = User.objects.get(username="marta")
        valid = RefreshToken.for_user(user)
        user.is_active = False
        user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {valid.access_token}")
        self.assertEqual(self.client.get("/api/me/").status_code, 401)

    def test_permissions_for_every_catalog_resource(self):
        user = User.objects.create_user("reader", password=self.data["password"])
        admin = User.objects.create_user(
            "staff", password=self.data["password"], is_staff=True
        )
        for resource in ["games", "categories", "venues"]:
            url = f"/api/{resource}/"
            self.client.credentials()
            self.assertEqual(self.client.get(url).status_code, 200)
            for method, path in [
                (self.client.post, url),
                (self.client.patch, url + "999/"),
                (self.client.delete, url + "999/"),
            ]:
                self.assertEqual(method(path, {}, format="json").status_code, 401)
            self.client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
            )
            for method, path in [
                (self.client.post, url),
                (self.client.patch, url + "999/"),
                (self.client.delete, url + "999/"),
            ]:
                response = method(path, {}, format="json")
                self.assertEqual(response.status_code, 403)
                self.assertIn("адміністратор", response.data["detail"])
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(admin).access_token}"
        )
        self.assertEqual(
            self.client.post(
                "/api/categories/", {"name": "Стратегії"}, format="json"
            ).status_code,
            201,
        )
        self.client.credentials()
        self.assertEqual(self.client.get("/api/me/").status_code, 401)
