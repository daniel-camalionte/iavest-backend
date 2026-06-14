from datetime import datetime, timedelta
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from flask_jwt_extended import create_access_token
from model.Usuario import UsuarioModel
from rule.Assinatura import AssinaturaRule
import config.env as memory


class AuthGoogleRule:

    @staticmethod
    def login(data):
        token = data.get("id_token")
        if not token:
            return {"success": False, "message": "id_token obrigatório"}, 400

        client_id = memory.google["CLIENT_ID"]
        if not client_id:
            return {"success": False, "message": "Google Auth não configurado"}, 500

        try:
            idinfo = id_token.verify_oauth2_token(token, grequests.Request(), client_id)
        except ValueError as e:
            return {"success": False, "message": f"Token inválido: {str(e)}"}, 401

        email  = idinfo.get("email")
        nome   = idinfo.get("name", "")

        if not email:
            return {"success": False, "message": "Email não disponível no token Google"}, 400

        modUsuario = UsuarioModel()
        usuario_data = modUsuario.where(['email', '=', email]).find()
        is_new = not isinstance(usuario_data, list) or len(usuario_data) == 0

        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        if is_new:
            save_result = modUsuario.save({
                "email":            email,
                "nome":             nome,
                "validacao_email":  1,
                "auth_provider":    "google",
                "created_at":       now,
                "updated_at":       now,
            })
            if not save_result or isinstance(save_result, tuple):
                return {"success": False, "message": "Erro ao criar usuário"}, 500

            modUsuario2 = UsuarioModel()
            usuario_data = modUsuario2.where(['email', '=', email]).find()
            if not isinstance(usuario_data, list) or len(usuario_data) == 0:
                return {"success": False, "message": "Erro ao recuperar usuário"}, 500

            try:
                AssinaturaRule().criar_trial(usuario_data[0]["id_usuario"])
            except Exception:
                pass

        usuario = usuario_data[0]
        id_usuario = usuario["id_usuario"]

        if not is_new and usuario.get("auth_provider") != "google":
            UsuarioModel().update({"auth_provider": "google", "updated_at": now}, id_usuario)

        requires_registration = not usuario.get("cpf_cnpj")

        token_data = {"id_usuario": id_usuario, "email": email}

        if requires_registration:
            jwt_token = create_access_token(
                identity={**token_data, "type": "temp_registration"},
                expires_delta=timedelta(minutes=120)
            )
        else:
            jwt_token = create_access_token(identity=token_data)

        response = {
            "success":               True,
            "message":               "Login realizado com sucesso",
            "token":                 jwt_token,
            "requires_registration": requires_registration,
        }

        if not requires_registration:
            response["user"] = {
                "id_usuario": id_usuario,
                "email":      usuario["email"],
                "nome":       usuario["nome"],
            }

        return response, 200
