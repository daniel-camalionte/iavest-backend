from model.Robos import RobosModel

class RobosRule():

    def __init__(self):
        pass

    def listar(self, id_usuario):
        modRobos = RobosModel()

        sql = """
            SELECT r.id_robos, r.nome, r.descricao, r.versao, r.arquivo_url, r.created_at
            FROM robos r
            INNER JOIN plano_usuario pu ON pu.id_plano = r.id_plano
            INNER JOIN assinatura a ON a.id_usuario = pu.id_usuario AND a.id_plano = pu.id_plano
            WHERE pu.id_usuario = %s
            AND a.status = 'active'
            ORDER BY r.nome ASC
        """

        robos = modRobos.execute(sql, [id_usuario])

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
