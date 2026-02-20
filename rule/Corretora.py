from model.Corretora import CorretoraModel

class CorretoraRule():

    def __init__(self):
        pass

    def listar(self):
        modCorretora = CorretoraModel()
        corretoras = modCorretora.where(['ativo', '=', 1]).order('destaque', 'DESC').order('nome_fantasia', 'ASC').find()

        if not corretoras:
            return {"success": True, "corretoras": []}, 200

        lista = []
        for corretora in corretoras:
            lista.append({
                "id": corretora["id_corretora"],
                "nome": corretora["nome_fantasia"],
                "codigo_b3": corretora["codigo_b3"],
                "destaque": bool(corretora["destaque"])
            })

        return {"success": True, "corretoras": lista}, 200
