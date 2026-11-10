from rest_framework.exceptions import ValidationError

from catalog.errors import api_exception_handler as catalog_exception_handler


def api_exception_handler(exc, context):
    response = catalog_exception_handler(exc, context)
    if response is not None and isinstance(exc, ValidationError):
        response.data["errors"] = exc.detail
    if response is not None and response.status_code == 401:
        response.data["detail"] = "Увійдіть в акаунт: дані входу або токен недійсні."
    return response
