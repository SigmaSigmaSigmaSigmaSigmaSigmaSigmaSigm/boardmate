from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.schema import ErrorResponse

from .serializers import RegisterSerializer, UserSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=RegisterSerializer, responses={201: UserSerializer, 400: ErrorResponse}
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {"username": ["Цей нік уже зайнятий."]}
            ) from None
        return Response(UserSerializer(user).data, status=201)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer, 401: ErrorResponse})
    def get(self, request):
        return Response(UserSerializer(request.user).data)
