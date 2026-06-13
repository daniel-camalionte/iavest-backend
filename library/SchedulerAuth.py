from flask import request
import config.env as memory


def check_scheduler_auth():
    """Valida o header X-Scheduler-Secret contra o SCHEDULER_SECRET da env.
    Retorna None se autorizado, ou (dict_erro, status_code) se não."""
    token    = request.headers.get("X-Scheduler-Secret", "")
    expected = memory.scheduler.get("SECRET", "")
    if not expected or token != expected:
        return {"error": "Não autorizado"}, 401
    return None
