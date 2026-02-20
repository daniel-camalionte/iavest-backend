from model.Plano import PlanoModel
import json

class PlanoRule():

    def __init__(self):
        pass

    def listar(self):
        modPlano = PlanoModel()
        planos = modPlano.where(['ativo', '=', 1]).order('id_plano', 'ASC').find()

        if not planos:
            return {"success": True, "planos": []}, 200

        lista = []
        for plano in planos:
            recursos = []
            if plano.get("recursos"):
                try:
                    recursos = json.loads(plano["recursos"])
                except:
                    recursos = []

            lista.append({
                "id": plano["id_plano"],
                "nome": plano["nome"],
                "descricao": plano["descricao"],
                "preco_mensal": float(plano["valor_original"]),
                "recursos": recursos,
                "destaque": bool(plano["destaque"])
            })

        return {"success": True, "planos": lista}, 200
