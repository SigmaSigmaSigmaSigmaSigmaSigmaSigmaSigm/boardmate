from django.http import JsonResponse
from django.urls import path, re_path

from .models import Category, Game, Venue
from .serializers import CategorySerializer, GameSerializer, VenueSerializer
from .views import ResourceDetail, ResourceList

urlpatterns = []
for resource, model, serializer in [
    ("categories", Category, CategorySerializer),
    ("games", Game, GameSerializer),
    ("venues", Venue, VenueSerializer),
]:
    options = {"model": model, "serializer_class": serializer}
    urlpatterns += [
        path(f"{resource}/", ResourceList.as_view(**options)),
        path(f"{resource}/<int:pk>/", ResourceDetail.as_view(**options)),
    ]


def not_found(request):
    return JsonResponse({"detail": "Ендпоінт не знайдено."}, status=404)


urlpatterns.append(re_path(r"^.*$", not_found))
