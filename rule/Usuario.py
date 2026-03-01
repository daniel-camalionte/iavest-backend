import re
from model.Usuario import UsuarioModel
from datetime import datetime


class UsuarioRule():

    def __init__(self):
        pass

    def get(self, id_usuario):
        modUsuario = UsuarioModel()
        usuario_data = modUsuario.find_one(id_usuario)

        if not usuario_data:
            return {"success": False, "message": "Usuário não encontrado"}, 404

        u = usuario_data[0]

        return {
            "success": True,
            "usuario": {
                "id_usuario": u["id_usuario"],
                "email": u["email"],
                "nome": u.get("nome"),
                "ddd": u.get("ddd"),
                "telefone": u.get("telefone"),
                "cpf_cnpj": u.get("cpf_cnpj"),
                "ultimo_login": str(u["hash_at"]) if u.get("hash_at") else None
            }
        }, 200

    def update(self, id_usuario, data):
        campos = {}

        if data.get("nome") is not None:
            if len(data["nome"]) < 3:
                return {"success": False, "message": "Nome inválido"}, 400
            campos["nome"] = data["nome"]

        if data.get("cpf_cnpj") is not None:
            campos["cpf_cnpj"] = re.sub(r'\D', '', data["cpf_cnpj"])

        if data.get("ddd") is not None:
            campos["ddd"] = data["ddd"]

        if data.get("telefone") is not None:
            campos["telefone"] = data["telefone"]

        if not campos:
            return {"success": False, "message": "Nenhum campo para atualizar"}, 400

        campos["updated_at"] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        modUsuario = UsuarioModel()
        modUsuario.update(campos, id_usuario)

        return {"success": True, "message": "Dados atualizados com sucesso"}, 200
