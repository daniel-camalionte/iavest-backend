from model.EtapaUsuario import EtapaUsuarioModel

class EtapaUsuarioRule():

    def registrar(self, id_usuario, data):
        id_etapa = data.get("id_etapa")

        if not id_etapa:
            return {"success": False, "message": "id_etapa é obrigatório"}, 400

        # Validação de duplicidade: chave composta id_etapa + id_usuario
        modCheck = EtapaUsuarioModel()
        existente = modCheck.where(['id_etapa', '=', id_etapa]).where(['id_usuario', '=', id_usuario]).find()

        if existente:
            return {"success": False, "message": "Etapa já registrada para este usuário"}, 409

        obj = {
            "id_etapa": id_etapa,
            "id_usuario": id_usuario
        }

        modEtapaUsuario = EtapaUsuarioModel()
        id_inserido = modEtapaUsuario.save(obj)

        if not id_inserido:
            return {"success": False, "message": "Erro ao registrar etapa"}, 500

        return {"success": True, "id_etapa_usuario": id_inserido}, 201

    def listar(self, id_usuario):
        modEtapaUsuario = EtapaUsuarioModel()
        registros = modEtapaUsuario.where(['id_usuario', '=', id_usuario]).find()

        if not registros:
            return {"success": True, "etapas": []}, 200

        etapas = [r["id_etapa"] for r in registros]

        return {"success": True, "etapas": etapas}, 200
