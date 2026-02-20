from model.Usuario import UsuarioModel
from library.SMTP import SMTP
from library.Funcao import Funcao
from datetime import datetime, timedelta, timezone
from flask_jwt_extended import create_access_token

class AuthRule():

    def __init__(self):
        pass

    def send_code(self, data):
        email = data.get("email")
        codigo = Funcao.rand(1, 6)
        hash_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        modUsuario = UsuarioModel()
        usuario_data = modUsuario.where(['email', '=', email]).find()

        # Verifica se é uma lista válida com resultados
        is_new_user = not isinstance(usuario_data, list) or len(usuario_data) == 0

        if is_new_user:
            # Novo usuário - início do cadastro
            modUsuario = UsuarioModel()
            save_result = modUsuario.save({
                "email": email,
                "hash": str(codigo),
                "hash_at": hash_at,
                "created_at": hash_at
            })

            if not save_result or isinstance(save_result, tuple):
                return {"success": False, "message": "Erro ao iniciar cadastro"}, 500
        else:
            # Usuário existente - atualiza código
            modUsuario = UsuarioModel()
            update_result = modUsuario.update({
                "hash": str(codigo),
                "hash_at": hash_at
            }, usuario_data[0]["id_usuario"])

            if not update_result:
                return {"success": False, "message": "Erro ao gerar código"}, 500

        try:
            smtp = SMTP()
            body = f"""
            <html>
            <body>
                <h2>Código de verificação</h2>
                <p>Seu código de verificação é: <strong>{codigo}</strong></p>
                <p>Este código expira em 10 minutos.</p>
            </body>
            </html>
            """

            result = smtp.send(email, "Código de Verificação", body)

            if not result:
                return {"success": False, "message": "Erro ao enviar email"}, 500
        except Exception as e:
            return {"success": False, "message": f"Erro SMTP: {str(e)}"}, 500

        return {
            "success": True,
            "message": "Código enviado com sucesso",
            "expires_in": 600
        }, 200

    def verify_code(self, data):
        email = data.get("email")
        code = str(data.get("code"))

        # Buscar usuário pelo email
        modUsuario = UsuarioModel()
        usuario_data = modUsuario.where(['email', '=', email]).find()

        if not isinstance(usuario_data, list) or len(usuario_data) == 0:
            return {"success": False, "message": "Código inválido ou expirado"}, 400

        usuario = usuario_data[0]

        # Verificar se o código corresponde (converter ambos para string)
        if str(usuario.get("hash")) != code:
            return {"success": False, "message": "Código inválido ou expirado"}, 400

        # Verificar se o código já foi usado (hash vazio)
        if not usuario.get("hash"):
            return {"success": False, "message": "Código inválido ou expirado"}, 400

        # Verificar se o código não expirou (10 minutos)
        hash_at = usuario.get("hash_at")
        if hash_at:
            now = datetime.utcnow()
            expiration_time = hash_at + timedelta(minutes=10)
            if now > expiration_time:
                return {"success": False, "message": "Código inválido ou expirado"}, 400

        # Marcar código como usado (limpar hash)
        modUsuario = UsuarioModel()
        modUsuario.update({
            "hash": "",
            "hash_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }, usuario["id_usuario"])

        # Gerar token temporário (30 minutos)
        token_data = {
            "id_usuario": usuario["id_usuario"],
            "email": email,
            "type": "temp_registration"
        }
        temp_token = create_access_token(identity=token_data, expires_delta=timedelta(minutes=120))

        # Verificar se requer cadastro (nome não preenchido)
        requires_registration = not usuario.get("nome")

        response = {
            "success": True,
            "message": "Código validado com sucesso",
            "token": temp_token,
            "requires_registration": requires_registration
        }

        # Se já cadastrado, retornar dados do usuário
        if not requires_registration:
            response["user"] = {
                "id_usuario": usuario["id_usuario"],
                "email": usuario["email"],
                "nome": usuario["nome"]
            }

        return response, 200

    def complete_registration(self, data, identity):
        # Validar se o token é do tipo temp_registration
        if identity.get("type") != "temp_registration":
            return {"success": False, "message": "Token temporário inválido ou expirado"}, 401

        id_usuario = identity.get("id_usuario")
        email_token = identity.get("email")

        # Validar se email do body corresponde ao do token
        if data.get("email") != email_token:
            return {"success": False, "message": "Email não corresponde ao token"}, 400

        nome = data.get("nome")
        cpf_cnpj = data.get("cpf_cnpj")
        ddd = data.get("ddd")
        telefone = data.get("telefone")

        # Validações básicas
        if not nome or len(nome) < 3:
            return {"success": False, "message": "Nome inválido"}, 400

        if not cpf_cnpj:
            return {"success": False, "message": "CPF/CNPJ inválido"}, 400

        # Atualizar usuário
        modUsuario = UsuarioModel()
        update_result = modUsuario.update({
            "nome": nome,
            "cpf_cnpj": cpf_cnpj,
            "ddd": ddd,
            "telefone": telefone,
            "validacao_email": 1,
            "updated_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }, id_usuario)

        if not update_result:
            return {"success": False, "message": "Erro ao completar cadastro"}, 500

        # Buscar dados atualizados
        modUsuario = UsuarioModel()
        usuario_data = modUsuario.find_one(id_usuario)

        if not usuario_data or not isinstance(usuario_data, list) or len(usuario_data) == 0:
            return {"success": False, "message": "Erro ao buscar usuário"}, 500

        usuario = usuario_data[0]

        # Gerar token definitivo
        token_data = {
            "id_usuario": id_usuario,
            "email": email_token
        }
        token = create_access_token(identity=token_data)

        return {
            "success": True,
            "message": "Cadastro concluído com sucesso",
            "token": token,
            "user": {
                "id": usuario["id_usuario"],
                "nome": usuario["nome"],
                "email": usuario["email"],
                "cpf_cnpj": usuario.get("cpf_cnpj"),
                "ddd": usuario.get("ddd"),
                "telefone": usuario.get("telefone"),
                "created_at": str(usuario.get("created_at"))
            }
        }, 200
