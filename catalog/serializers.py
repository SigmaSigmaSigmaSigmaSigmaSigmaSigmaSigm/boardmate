from rest_framework import serializers

from .errors import Conflict
from .models import Category, Game, Venue


class StrictModelSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {"non_field_errors": ["Очікується JSON-об’єкт."]}
            )
        if not data:
            raise serializers.ValidationError(
                {"non_field_errors": ["Передайте поля для створення або зміни."]}
            )
        unknown = set(data) - set(self.fields)
        readonly = {
            name for name in data if name in self.fields and self.fields[name].read_only
        }
        if unknown or readonly:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        f"Недозволені поля: {', '.join(sorted(unknown | readonly))}."
                    ]
                }
            )
        return super().to_internal_value(data)


class CategorySerializer(StrictModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]
        extra_kwargs = {"name": {"validators": []}}

    def validate_name(self, value):
        categories = Category.objects.filter(name=value)
        if self.instance:
            categories = categories.exclude(pk=self.instance.pk)
        if categories.exists():
            raise Conflict("Категорія з такою назвою вже існує. Оберіть іншу назву.")
        return value


class GameSerializer(StrictModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all()
    )

    class Meta:
        model = Game
        fields = [
            "id",
            "name",
            "description",
            "category_id",
            "min_players",
            "max_players",
            "duration_minutes",
        ]

    def validate(self, attrs):
        minimum = attrs.get("min_players", getattr(self.instance, "min_players", None))
        maximum = attrs.get("max_players", getattr(self.instance, "max_players", None))
        if minimum > maximum:
            raise serializers.ValidationError(
                "Мінімальна кількість гравців не може перевищувати максимальну."
            )
        return attrs


class VenueSerializer(StrictModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "city", "address", "description"]
