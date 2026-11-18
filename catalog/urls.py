from django.http import JsonResponse
from django.urls import path, re_path

from .models import Category, Game, Venue
from .serializers import CategorySerializer, GameSerializer, VenueSerializer
from .views import (
    GameQuerySerializer,
    ListQuerySerializer,
    ResourceDetail,
    ResourceList,
    VenueQuerySerializer,
)

urlpatterns = []
for resource, model, serializer, query in [
    ("categories", Category, CategorySerializer, ListQuerySerializer),
    ("games", Game, GameSerializer, GameQuerySerializer),
    ("venues", Venue, VenueSerializer, VenueQuerySerializer),
]:
    options = {"model": model, "serializer_class": serializer}
    urlpatterns += [
        path(
            f"{resource}/",
            ResourceList.as_view(query_serializer_class=query, **options),
        ),
        path(f"{resource}/<int:pk>/", ResourceDetail.as_view(**options)),
    ]


def not_found(request):
    return JsonResponse({"detail": "Ендпоінт не знайдено."}, status=404)


urlpatterns.append(re_path(r"^.*$", not_found))
