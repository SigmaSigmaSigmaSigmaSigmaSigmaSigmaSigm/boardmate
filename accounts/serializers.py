from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "is_staff"]
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, trim_whitespace=False
    )
    password_confirmation = serializers.CharField(
        write_only=True, max_length=128, trim_whitespace=False
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "password_confirmation",
        ]
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": True, "max_length": 150},
            "last_name": {"required": False, "allow_blank": True, "max_length": 150},
        }

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError(
                {"non_field_errors": ["Передані невідомі поля."]}
            )
        return super().to_internal_value(data)

    def validate(self, attrs):
        errors = {}
        if attrs["password"] != attrs["password_confirmation"]:
            errors["password_confirmation"] = ["Паролі не збігаються."]
        user = User(
            username=attrs["username"],
            email=attrs["email"],
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs["password"], user)
        except DjangoValidationError as exc:
            errors["password"] = exc.messages
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirmation")
        return User.objects.create_user(**validated_data)
