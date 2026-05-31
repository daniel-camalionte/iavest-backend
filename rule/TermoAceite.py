from model.TermoAceite import TermoAceiteModel


class TermoAceiteRule:

    TIPOS_VALIDOS = {'cadastro', 'assinatura'}

    @staticmethod
    def registrar(tipo_aceite, termo_versao, ip_address, user_agent, id_usuario=None):
        if not tipo_aceite:
            return {"error": "Campo 'tipo_aceite' é obrigatório"}, 400

        if tipo_aceite not in TermoAceiteRule.TIPOS_VALIDOS:
            return {
                "error":   f"'tipo_aceite' inválido: {tipo_aceite}",
                "aceitos": sorted(TermoAceiteRule.TIPOS_VALIDOS),
            }, 400

        if not termo_versao:
            return {"error": "Campo 'termo_versao' é obrigatório"}, 400

        record = {
            "tipo_aceite":  tipo_aceite,
            "termo_versao": termo_versao,
            "ip_address":   ip_address,
            "user_agent":   user_agent,
        }

        if id_usuario:
            record["id_usuario"] = id_usuario

        inserted_id = TermoAceiteModel().save(record)

        return {"id_termo_aceite": inserted_id, "status": "aceito"}, 201
