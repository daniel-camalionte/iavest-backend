from model.Robos import RobosModel
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

        modRobos = RobosModel()

        sql = """
            SELECT r.id_robos, r.nome, r.descricao, r.versao, r.arquivo_url, r.created_at
            FROM robos r
            WHERE r.id_plano = %s
            ORDER BY r.nome ASC
        """

        robos = modRobos.execute(sql, [id_plano])

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
                "created_at": str(robo["created_at"]) if robo["created_at"] else None
            })

        return {"success": True, "robos": lista}, 200
