import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import PublicReadAdminWrite

from .errors import Conflict
from .models import Category
from .schema import CatalogSchema

logger = logging.getLogger("boardmate.api")


class ListQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(
        min_value=1, default=1, help_text="20 записів на сторінку."
    )


class GameQuerySerializer(ListQuerySerializer):
    search = serializers.CharField(
        required=False, allow_blank=True, help_text="Частина назви гри."
    )
    category_id = serializers.IntegerField(min_value=1, required=False)
    players = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="Кількість гравців у межах min_players і max_players.",
    )
    ordering = serializers.ChoiceField(
        choices=("name", "duration_minutes", "-duration_minutes"),
        required=False,
        help_text="Типово name. Мінус означає спадний порядок.",
    )


class VenueQuerySerializer(ListQuerySerializer):
    search = serializers.CharField(
        required=False, allow_blank=True, help_text="Частина назви місця."
    )
    city = serializers.CharField(required=False, help_text="Повна назва міста.")


class ResourceList(APIView):
    permission_classes = [PublicReadAdminWrite]
    schema = CatalogSchema()

    model = None
    serializer_class = None
    query_serializer_class = ListQuerySerializer

    def get(self, request):
        query = self.query_serializer_class(data=request.query_params)
        if set(request.query_params) - set(query.fields):
            raise serializers.ValidationError("Невідомі параметри запиту.")
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
            obj = serializer.save()
        logger.info("Catalog created resource=%s id=%d", self.model.__name__, obj.pk)
        return Response(serializer.data, status=201)


class ResourceDetail(APIView):
    permission_classes = [PublicReadAdminWrite]
    schema = CatalogSchema()

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
        logger.info("Catalog updated resource=%s id=%d", self.model.__name__, obj.pk)
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
        logger.info("Catalog deleted resource=%s id=%d", self.model.__name__, pk)
        return Response(status=204)
