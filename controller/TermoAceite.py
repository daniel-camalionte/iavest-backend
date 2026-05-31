from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity

from rule.TermoAceite import TermoAceiteRule


class TermoAceiteController(MethodView):

    @jwt_required
    def post(self):
        body = request.get_json() or {}

        ip_address = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr
            or ""
        )

        identity   = get_jwt_identity()
        id_usuario = identity.get("id_usuario") if isinstance(identity, dict) else identity

        return TermoAceiteRule.registrar(
            tipo_aceite=body.get("tipo_aceite"),
            termo_versao=body.get("termo_versao"),
            ip_address=ip_address,
            user_agent=request.headers.get("User-Agent", ""),
            id_usuario=id_usuario,
        )
