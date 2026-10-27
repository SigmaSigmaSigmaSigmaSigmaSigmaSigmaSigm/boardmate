from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Category, Game, Venue


class CatalogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Стратегії")
        self.game_data = {
            "name": "Forest paths",
            "description": "Настільна гра про подорож лісом.",
            "category_id": self.category.pk,
            "min_players": 2,
            "max_players": 4,
            "duration_minutes": 45,
        }

    def assert_error(self, response, status):
        self.assertEqual(response.status_code, status)
        self.assertEqual(set(response.json()), {"detail"})
        self.assertIsInstance(response.json()["detail"], str)
        self.assertTrue(response.json()["detail"])

    def test_crud_for_all_resources(self):
        for resource, data, patch in [
            ("categories", {"name": "Сімейні"}, {"name": "Кооперативні"}),
            ("games", self.game_data, {"max_players": 5}),
            (
                "venues",
                {
                    "name": "Клуб",
                    "city": "Київ",
                    "address": "Вулиця, 1",
                    "description": "Кафе",
                },
                {"city": "Львів"},
            ),
        ]:
            with self.subTest(resource=resource):
                url = f"/api/{resource}/"
                response = self.client.post(url, data, format="json")
                self.assertEqual(response.status_code, 201, response.data)
                pk = response.data["id"]
                self.assertEqual(
                    self.client.get(url).data["count"],
                    1 if resource != "categories" else 2,
                )
                detail = f"{url}{pk}/"
                self.assertEqual(self.client.get(detail).data["id"], pk)
                changed = self.client.patch(detail, patch, format="json")
                self.assertEqual(changed.status_code, 200)
                for field, value in patch.items():
                    self.assertEqual(changed.data[field], value)
                deleted = self.client.delete(detail)
                self.assertEqual(deleted.status_code, 204)
                self.assertEqual(deleted.content, b"")
                self.assert_error(self.client.get(detail), 404)

    def test_protected_category_and_unique_name(self):
        game = self.client.post("/api/games/", self.game_data, format="json").data
        url = f"/api/categories/{self.category.pk}/"
        blocked = self.client.delete(url)
        self.assert_error(blocked, 409)
        self.assertIn("1 ігор", blocked.data["detail"])
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assert_error(
            self.client.post(
                "/api/categories/", {"name": " Стратегії "}, format="json"
            ),
            409,
        )
        self.assertEqual(
            self.client.patch(url, {"name": "Стратегії"}, format="json").status_code,
            200,
        )
        self.client.delete(f"/api/games/{game['id']}/")
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_invalid_game_data_and_partial_validation(self):
        for patch in [
            {"min_players": 0},
            {"max_players": 1},
            {"duration_minutes": -5},
            {"category_id": 999999},
            {"name": " "},
            {"description": "x" * 2001},
            {"name": "x" * 121},
            {"min_players": "bad"},
            {"name": None},
        ]:
            with self.subTest(patch=patch):
                self.assert_error(
                    self.client.post(
                        "/api/games/", self.game_data | patch, format="json"
                    ),
                    400,
                )
        response = self.client.post("/api/games/", self.game_data, format="json")
        url = f"/api/games/{response.data['id']}/"
        self.assert_error(
            self.client.patch(url, {"min_players": 6}, format="json"), 400
        )
        self.assertEqual(Game.objects.get(pk=response.data["id"]).min_players, 2)

    def test_bad_body_missing_object_and_unsupported_method(self):
        for resource in ["categories", "games", "venues"]:
            url = f"/api/{resource}/"
            for body in [{}, {"id": 3}, {"unknown": "x"}, [], "text"]:
                with self.subTest(resource=resource, body=body):
                    self.assert_error(self.client.post(url, body, format="json"), 400)
            for method in [self.client.get, self.client.patch, self.client.delete]:
                self.assert_error(method(f"{url}999999/"), 404)
            self.assert_error(self.client.put(url, {}, format="json"), 405)
            self.assert_error(
                self.client.post(url, '{"broken"', content_type="application/json"), 400
            )
        self.assert_error(self.client.get("/api/missing/"), 404)

    def test_filters_sorting_and_pagination(self):
        self.client.post("/api/games/", self.game_data, format="json")
        self.client.post(
            "/api/games/",
            self.game_data | {"name": "Other", "duration_minutes": 90},
            format="json",
        )
        response = self.client.get(
            "/api/games/",
            {"search": "forest", "players": 3, "category_id": self.category.pk},
        )
        self.assertEqual(response.data["count"], 1)
        response = self.client.get("/api/games/", {"ordering": "-duration_minutes"})
        self.assertEqual(response.data["results"][0]["name"], "Other")
        response = self.client.get("/api/games/", {"page": 999})
        self.assertEqual(response.data, {"count": 2, "page": 999, "results": []})
        self.assertEqual(
            self.client.get("/api/games/", {"page": 10**30}).data["results"], []
        )
        for query in [
            {"page": 0},
            {"players": "bad"},
            {"ordering": "id"},
            {"unknown": "x"},
        ]:
            self.assert_error(self.client.get("/api/games/", query), 400)
        Venue.objects.create(name="Club", city="Kyiv", address="A", description="D")
        self.assertEqual(
            self.client.get("/api/venues/", {"city": "kyiv", "search": "club"}).data[
                "count"
            ],
            1,
        )
        Category.objects.bulk_create(
            [Category(name=f"Category {i}") for i in range(22)]
        )
        self.assertEqual(len(self.client.get("/api/categories/").data["results"]), 20)
        self.assertEqual(
            len(self.client.get("/api/categories/", {"page": 2}).data["results"]), 3
        )

    def test_database_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Game.objects.create(
                category=self.category,
                name="Invalid",
                description="D",
                min_players=4,
                max_players=2,
                duration_minutes=45,
            )

    def test_cors_allowed_origin_and_preflight(self):
        origin = "http://localhost:5500"
        response = self.client.get("/api/games/", HTTP_ORIGIN=origin)
        self.assertEqual(response["Access-Control-Allow-Origin"], origin)
        response = self.client.options(
            "/api/games/",
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], origin)
        response = self.client.get(
            "/api/games/", HTTP_ORIGIN="http://untrusted.example"
        )
        self.assertNotIn("Access-Control-Allow-Origin", response)
