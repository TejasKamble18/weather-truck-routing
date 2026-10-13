from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_handler


class PlannerError(APIException):
    def __init__(self, detail, code="upstream_error", status=502):
        self.status_code = status
        self.error_code = code
        super().__init__(detail, code)


def exception_handler(exc, context):
    response = drf_handler(exc, context)
    if response is not None:
        detail = response.data
        if isinstance(detail, dict) and set(detail) == {"detail"}:
            detail = detail["detail"]
        response.data = {
            "error": getattr(
                exc,
                "error_code",
                "invalid_input" if response.status_code == 400 else "request_error",
            ),
            "detail": detail,
        }
    return response
