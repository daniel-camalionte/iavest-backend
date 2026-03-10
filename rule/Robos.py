from model.Estrategia import EstrategiaModel
from model.Assinatura import AssinaturaModel

class RobosRule():

    def __init__(self):
        pass

    def listar(self, id_usuario):
        modAssinatura = AssinaturaModel()
        assinatura = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).find()

        if not assinatura:
            return {"success": False, "message": "Nenhum robô disponível. Verifique sua assinatura."}, 404

        id_plano = assinatura[0]["id_plano"]

        sql = """
            SELECT
                e.id_estrategia AS id_robos,
                e.robo_nome     AS nome,
                e.robo_descricao AS descricao,
                e.robo_versao   AS versao,
                e.robo_url      AS arquivo_url,
                e.robo_operacao AS operacao,
                e.created_at
            FROM estrategia e
            INNER JOIN plano_estrategia pe ON pe.id_estrategia = e.id_estrategia
            WHERE pe.id_plano = %s
              AND e.robo_url IS NOT NULL
              AND e.status = 'active'
            ORDER BY e.robo_nome ASC
        """

        robos = EstrategiaModel().execute(sql, [id_plano])

        if not robos:
            return {"success": False, "message": "Nenhum robô disponível. Verifique sua assinatura."}, 404

        lista = []
        for robo in robos:
            lista.append({
                "id": robo["id_robos"],
                "nome": robo["nome"],
                "descricao": robo["descricao"],
                "versao": robo["versao"],
                "arquivo_url": robo["arquivo_url"],
                "operacao": robo["operacao"],
                "created_at": str(robo["created_at"]) if robo["created_at"] else None
            })

        return {"success": True, "robos": lista}, 200
