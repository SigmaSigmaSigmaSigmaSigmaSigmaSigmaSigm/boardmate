from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import Game


class GameAPITests(TestCase):
    fixtures = ["games.json"]
    games_url = "/api/games/"
    game_url = "/api/games/101/"
    new_game = {
        "name": "Mountain road",
        "description": "Гра про подорож горами.",
        "category_id": 10,
        "min_players": 2,
        "max_players": 5,
        "duration_minutes": 60,
    }

    def setUp(self):
        self.client = APIClient()

    def sign_in(self, username):
        user = get_user_model().objects.get(username=username)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}"
        )

    def test_guest_can_list_filter_and_read_games(self):
        params = {"search": "forest", "players": 3, "category_id": 10, "page": 1}
        response = self.client.get(self.games_url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual([game["id"] for game in response.data["results"]], [101])
        detail = self.client.get(self.game_url)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data, response.data["results"][0])
        self.assertEqual(detail.data["category_id"], 10)

    def test_admin_can_create_update_and_delete_game(self):
        self.sign_in("test-admin")
        with self.assertLogs("boardmate.api", level="INFO") as logs:
            created = self.client.post(self.games_url, self.new_game, format="json")
            self.assertEqual(created.status_code, 201, created.data)
            pk = created.data["id"]
            self.assertEqual(Game.objects.get(pk=pk).duration_minutes, 60)
            url = f"{self.games_url}{pk}/"
            updated = self.client.patch(url, {"max_players": 6}, format="json")
            self.assertEqual(updated.status_code, 200, updated.data)
            game = Game.objects.get(pk=pk)
            self.assertEqual(game.max_players, 6)
            self.assertEqual(game.name, self.new_game["name"])
            deleted = self.client.delete(url)
            self.assertEqual(deleted.status_code, 204)
            self.assertFalse(Game.objects.filter(pk=pk).exists())
        self.assertEqual(
            [record.getMessage() for record in logs.records],
            [
                f"Catalog {action} resource=Game id={pk}"
                for action in ("created", "updated", "deleted")
            ],
        )

    def test_writes_require_jwt_and_staff_role(self):
        for username, status in [(None, 401), ("test-player", 403)]:
            if username:
                self.sign_in(username)
            for method, url, data in [
                (self.client.post, self.games_url, self.new_game),
                (self.client.patch, self.game_url, {"max_players": 6}),
                (self.client.delete, self.game_url, {}),
            ]:
                with self.subTest(username=username, method=method.__name__):
                    response = method(url, data, format="json")
                    self.assertEqual(response.status_code, status)
                    self.assertIn("detail", response.data)
        self.assertEqual(Game.objects.count(), 2)
        self.assertEqual(Game.objects.get(pk=101).max_players, 4)

    def test_invalid_create_and_partial_update_keep_database_unchanged(self):
        self.sign_in("test-admin")
        invalid = self.new_game | {"category_id": 999, "duration_minutes": 0}
        response = self.client.post(self.games_url, invalid, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            set(response.data["errors"]), {"category_id", "duration_minutes"}
        )
        self.assertEqual(Game.objects.count(), 2)
        response = self.client.patch(self.game_url, {"min_players": 5}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("non_field_errors", response.data["errors"])
        self.assertEqual(Game.objects.get(pk=101).min_players, 2)

    def test_delete_unknown_game_returns_json_404(self):
        self.sign_in("test-admin")
        response = self.client.delete("/api/games/999/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.data)
        self.assertEqual(Game.objects.count(), 2)

    def test_rejected_login_log_excludes_credentials_and_query(self):
        with self.assertLogs("boardmate.api", level="WARNING") as logs:
            response = self.client.post(
                "/api/auth/login/?ignored=private-query",
                {"username": "test-player", "password": "private-password"},
                format="json",
                HTTP_AUTHORIZATION="Bearer private-token",
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            [record.getMessage() for record in logs.records],
            ["API rejected route=api/auth/login/ status=401"],
        )

    def test_openapi_describes_game_filters_and_permissions(self):
        response = self.client.get("/api/schema/", {"format": "json"})
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        collection = schema["paths"][self.games_url]
        detail = schema["paths"]["/api/games/{id}/"]
        self.assertEqual(set(collection), {"get", "post"})
        self.assertEqual(set(detail), {"get", "patch", "delete"})
        self.assertEqual(
            {p["name"] for p in collection["get"]["parameters"]},
            {"category_id", "ordering", "page", "players", "search"},
        )
        self.assertIn({}, collection["get"]["security"])
        self.assertEqual(collection["post"]["security"], [{"jwtAuth": []}])
        self.assertTrue(detail["patch"]["requestBody"]["required"])
        self.assertNotIn("content", detail["delete"]["responses"]["204"])
        self.assertEqual(
            schema["components"]["securitySchemes"]["jwtAuth"]["scheme"], "bearer"
        )
        self.assertEqual(
            set(schema["components"]["schemas"]["GamePage"]["properties"]),
            {"count", "page", "results"},
        )
        response = self.client.get("/api/docs/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/api/schema/")
