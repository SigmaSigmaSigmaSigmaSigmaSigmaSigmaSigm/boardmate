import logging

from rest_framework.exceptions import ValidationError

from catalog.errors import api_exception_handler as catalog_exception_handler

logger = logging.getLogger("boardmate.api")


def api_exception_handler(exc, context):
    response = catalog_exception_handler(exc, context)
    if response is not None and isinstance(exc, ValidationError):
        response.data["errors"] = exc.detail
    if response is not None and response.status_code == 401:
        response.data["detail"] = "Увійдіть в акаунт: дані входу або токен недійсні."
    match = getattr(context.get("request"), "resolver_match", None)
    route = match.route if match else type(context.get("view")).__name__
    if response is None or response.status_code >= 500:
        logger.error("API failure route=%s type=%s", route, type(exc).__name__)
    elif response.status_code in (401, 403, 409):
        logger.warning("API rejected route=%s status=%d", route, response.status_code)
    return response
