import base64
from flask import request
import config.env as memory


def check_scheduler_auth():
    """Valida o SCHEDULER_SECRET via X-Scheduler-Secret header ou HTTP Basic Auth (password).
    Retorna None se autorizado, ou (dict_erro, status_code) se não."""
    expected = memory.scheduler.get("SECRET", "")
    if not expected:
        return {"error": "Não autorizado"}, 401

    if request.headers.get("X-Scheduler-Secret") == expected:
        return None

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            _, password = decoded.split(":", 1)
            if password == expected:
                return None
        except Exception:
            pass

    return {"error": "Não autorizado"}, 401
