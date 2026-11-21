import base64
import binascii
from hmac import compare_digest

from fastapi import Request, Response


def install_access_gate(app, username: str, password: str, *, public_health: bool = False):
    """Temporary team access while account-based login is not yet implemented."""
    @app.middleware("http")
    async def require_password(request: Request, call_next):
        if public_health and request.method == "GET" and request.url.path == "/api/health":
            return await call_next(request)
        supplied_user, supplied_password = "", ""
        scheme, _, value = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() == "basic":
            try:
                supplied_user, supplied_password = base64.b64decode(value, validate=True).decode("utf-8").split(":", 1)
            except (ValueError, UnicodeDecodeError, binascii.Error):
                pass
        valid = compare_digest(supplied_user.encode(), username.encode()) & compare_digest(supplied_password.encode(), password.encode())
        if not valid:
            return Response("Team credentials required.", status_code=401, headers={
                "WWW-Authenticate":'Basic realm="Campus Find Team", charset="UTF-8"',
                "Cache-Control":"no-store",
            })
        response = await call_next(request)
        response.headers["Cache-Control"] = "private, no-store"
        return response
