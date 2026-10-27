from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .errors import Conflict
from .models import Category, Game


class ListQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    search = serializers.CharField(required=False, allow_blank=True)
    category_id = serializers.IntegerField(min_value=1, required=False)
    players = serializers.IntegerField(min_value=1, required=False)
    city = serializers.CharField(required=False)
    ordering = serializers.CharField(required=False)


class ResourceList(APIView):
    model = None
    serializer_class = None

    def get(self, request):
        allowed = {"page"}
        if self.model is Game:
            allowed |= {"search", "category_id", "players", "ordering"}
        elif self.model is not Category:
            allowed |= {"search", "city"}
        if set(request.query_params) - allowed:
            raise serializers.ValidationError("Невідомі параметри запиту.")
        query = ListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        records = self.model.objects.all()
        if "search" in params:
            records = records.filter(name__icontains=params["search"])
        if "city" in params:
            records = records.filter(city__iexact=params["city"])
        if "category_id" in params:
            records = records.filter(category_id=params["category_id"])
        if "players" in params:
            records = records.filter(
                min_players__lte=params["players"], max_players__gte=params["players"]
            )
        ordering = params.get("ordering", "name")
        if ordering not in {"name", "duration_minutes", "-duration_minutes"}:
            raise serializers.ValidationError("Недозволене сортування.")
        records = records.order_by(ordering, "id")
        page = params["page"]
        count = records.count()
        start = (page - 1) * 20
        records = records[start : start + 20] if start < count else []
        return Response(
            {
                "count": count,
                "page": page,
                "results": self.serializer_class(records, many=True).data,
            }
        )

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
        return Response(serializer.data, status=201)


class ResourceDetail(APIView):
    model = None
    serializer_class = None

    def get(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        return Response(self.serializer_class(obj).data)

    def patch(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        serializer = self.serializer_class(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        if isinstance(obj, Category):
            count = obj.games.count()
            if count:
                raise Conflict(
                    f"Неможливо видалити категорію: до неї належать {count} ігор. "
                    "Спочатку видаліть ці ігри або змініть їхню категорію."
                )
        with transaction.atomic():
            obj.delete()
        return Response(status=204)
