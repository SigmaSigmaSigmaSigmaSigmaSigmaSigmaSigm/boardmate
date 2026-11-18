from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import SAFE_METHODS


class ErrorResponse(serializers.Serializer):
    detail = serializers.CharField()
    errors = serializers.JSONField(required=False, help_text="Помилки полів, якщо є.")


class CatalogSchema(AutoSchema):
    def get_operation(self, path, path_regex, path_prefix, method, registry):
        operation = super().get_operation(
            path, path_regex, path_prefix, method, registry
        )
        if operation and method == "PATCH":
            operation["requestBody"]["required"] = True
        return operation

    def get_operation_id(self):
        if self.method == "GET" and hasattr(self.view, "query_serializer_class"):
            return f"{self.get_tags()[0]}_list"
        return super().get_operation_id()

    def get_auth(self):
        auth = super().get_auth()
        return [*auth, {}] if self.method in SAFE_METHODS else auth

    def get_override_parameters(self):
        if self.method == "GET" and hasattr(self.view, "query_serializer_class"):
            return [self.view.query_serializer_class]
        return []

    def get_description(self):
        if self.method == "GET":
            return "Публічне читання. JWT необов’язковий, але переданий токен має бути чинним."
        if self.method == "PATCH":
            return "Потрібен access JWT адміністратора (is_staff=True). Передайте хоча б одне поле для зміни."
        return (
            "Потрібен access JWT користувача з правами адміністратора (is_staff=True)."
        )

    def get_response_serializers(self):
        serializer = self.view.serializer_class
        responses = {401: OpenApiResponse(ErrorResponse, "Немає чинного токена.")}
        if self.method == "GET":
            if hasattr(self.view, "query_serializer_class"):
                response = inline_serializer(
                    name=f"{self.view.model.__name__}Page",
                    fields={
                        "count": serializers.IntegerField(),
                        "page": serializers.IntegerField(),
                        "results": serializer(many=True),
                    },
                )
                return {200: response, 400: ErrorResponse, **responses}
            return {200: serializer, 404: ErrorResponse, **responses}

        responses[403] = OpenApiResponse(
            ErrorResponse, "Потрібні права адміністратора."
        )
        responses[409] = OpenApiResponse(ErrorResponse, "Конфлікт даних.")
        if self.method != "POST":
            responses[404] = ErrorResponse
        if self.method == "DELETE":
            return {204: None, **responses}
        return {
            201 if self.method == "POST" else 200: serializer,
            400: ErrorResponse,
            415: OpenApiResponse(ErrorResponse, "Тіло запиту має бути JSON."),
            **responses,
        }

    def get_examples(self):
        if self.view.model.__name__ == "Game" and self.method == "POST":
            game = {
                "name": "Лісові стежки",
                "description": "Гра про подорож лісом.",
                "category_id": 1,
                "min_players": 2,
                "max_players": 4,
                "duration_minutes": 45,
            }
            return [
                OpenApiExample(
                    "Нова гра (категорія 1 має існувати)", value=game, request_only=True
                ),
                OpenApiExample(
                    "Створена гра",
                    value={"id": 7, **game},
                    response_only=True,
                    status_codes=[201],
                ),
            ]
        return []
