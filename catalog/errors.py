from django.db import IntegrityError
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


class Conflict(APIException):
    status_code = 409
    default_detail = "Дія суперечить поточному стану даних."


def api_exception_handler(exc, context):
    if isinstance(exc, IntegrityError):
        return Response(
            {"detail": "Конфлікт даних. Перевірте унікальність і пов’язані записи."},
            status=409,
        )
    response = exception_handler(exc, context)
    if response is not None:
        data = response.data
        if isinstance(data, dict) and "detail" in data:
            detail = str(data["detail"])
        elif isinstance(data, dict):
            detail = "; ".join(
                f"{field}: {', '.join(map(str, messages))}"
                for field, messages in data.items()
            )
        else:
            detail = "; ".join(map(str, data))
        response.data = {"detail": detail}
    return response
