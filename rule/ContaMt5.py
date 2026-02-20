from model.MetatraderConfigs import MetatraderConfigsModel
from model.Symbols import SymbolsModel
import string
import random

class ContaMt5Rule():

    def __init__(self):
        pass

    def _gerar_senha(self, tamanho=10):
        caracteres = string.ascii_letters + string.digits
        return ''.join(random.choices(caracteres, k=tamanho))

    def criar(self, id_usuario, data):
        campos_obrigatorios = ["id_corretora", "account", "account_number"]
        for campo in campos_obrigatorios:
            if not data.get(campo):
                return {"success": False, "message": "Campo {} é obrigatório".format(campo)}, 400

        # Validar duplicidade (id_usuario + account_number) - UNIQUE KEY no banco
        modCheck = MetatraderConfigsModel()
        duplicado = modCheck.where(['id_usuario', '=', id_usuario]).where(['account_number', '=', data["account_number"]]).find()

        if duplicado:
            return {"success": False, "message": "Já existe uma conta com este account_number"}, 409

        # Buscar symbol ativo do tipo WIN
        modSymbols = SymbolsModel()
        symbol = modSymbols.where(['type', '=', 'WIN']).where(['ativo', '=', 1]).limit(1).find()

        if not symbol:
            return {"success": False, "message": "Nenhum ativo disponível"}, 500

        senha = self._gerar_senha()

        obj = {
            "id_usuario": id_usuario,
            "id_corretora": data["id_corretora"],
            "id_symbols": symbol[0]["id_symbols"],
            "account": data["account"],
            "account_number": data["account_number"],
            "password": senha,
            "status": data.get("status", "active")
        }

        modMt5 = MetatraderConfigsModel()
        id_inserido = modMt5.save(obj)

        if not id_inserido:
            return {"success": False, "message": "Erro ao cadastrar conta MT5"}, 500

        # Buscar registro criado
        modMt5 = MetatraderConfigsModel()
        registro = modMt5.find_one(id_inserido)

        if not registro:
            return {"success": False, "message": "Erro ao buscar conta criada"}, 500

        conta = registro[0]

        return {
            "success": True,
            "conta": {
                "id": conta["id_metatrader_configs"],
                "account_number": conta["account_number"],
                "password": conta["password"],
                "created_at": str(conta["created_at"]) if conta["created_at"] else None
            }
        }, 201

    def deletar(self, id_usuario, id_conta):
        modMt5 = MetatraderConfigsModel()
        registro = modMt5.where(['id_metatrader_configs', '=', id_conta]).where(['id_usuario', '=', id_usuario]).find()

        if not registro:
            return {"success": False, "message": "Conta MT5 não encontrada"}, 404

        modMt5 = MetatraderConfigsModel()
        modMt5.delete(id_conta)

        return {"success": True, "message": "Conta MT5 removida com sucesso"}, 200

    def atualizar(self, id_usuario, id_conta, data):
        # Verificar se a conta pertence ao usuario
        modMt5 = MetatraderConfigsModel()
        registro = modMt5.where(['id_metatrader_configs', '=', id_conta]).where(['id_usuario', '=', id_usuario]).find()

        if not registro:
            return {"success": False, "message": "Conta MT5 não encontrada"}, 404

        obj = {}
        campos_permitidos = ["id_corretora", "account", "account_number", "password", "status"]
        for campo in campos_permitidos:
            if campo in data:
                obj[campo] = data[campo]

        if not obj:
            return {"success": False, "message": "Nenhum campo para atualizar"}, 400

        # Validar duplicidade (id_usuario + account_number) - UNIQUE KEY no banco
        account_number = data.get("account_number", registro[0]["account_number"])

        modCheck = MetatraderConfigsModel()
        duplicado = modCheck.where(['id_usuario', '=', id_usuario]).where(['account_number', '=', account_number]).where(['id_metatrader_configs', '!=', id_conta]).find()

        if duplicado:
            return {"success": False, "message": "Já existe uma conta com este account_number"}, 409

        modMt5 = MetatraderConfigsModel()
        modMt5.update(obj, id_conta)

        return {"success": True, "message": "Conta MT5 atualizada com sucesso"}, 200

    def listar(self, id_usuario, filtros):
        per_page = 10
        page = filtros.get("page", 1)
        if page < 1:
            page = 1
        offset = (page - 1) * per_page

        # Montar condicoes dinamicas
        where = "WHERE mc.id_usuario = %s"
        params = [id_usuario]

        if filtros.get("account"):
            where += " AND mc.account = %s"
            params.append(filtros["account"])

        if filtros.get("account_number"):
            where += " AND mc.account_number = %s"
            params.append(filtros["account_number"])

        # Contar total para paginacao
        sql_count = """
            SELECT COUNT(*) as total
            FROM metatrader_configs mc
            INNER JOIN corretora c ON c.id_corretora = mc.id_corretora
            INNER JOIN symbols s ON s.id_symbols = mc.id_symbols
            {}
        """.format(where)

        modMt5 = MetatraderConfigsModel()
        count_result = modMt5.execute(sql_count, params)
        total = count_result[0]["total"] if count_result else 0

        # Buscar contas com JOIN
        sql = """
            SELECT mc.id_metatrader_configs, mc.id_corretora, c.nome_fantasia,
                   mc.id_symbols, s.ticker as server,
                   mc.account, mc.account_number, mc.password,
                   mc.status, mc.created_at
            FROM metatrader_configs mc
            INNER JOIN corretora c ON c.id_corretora = mc.id_corretora
            INNER JOIN symbols s ON s.id_symbols = mc.id_symbols
            {}
            ORDER BY mc.created_at DESC
            LIMIT %s OFFSET %s
        """.format(where)

        params_query = params + [per_page, offset]

        modMt5 = MetatraderConfigsModel()
        contas = modMt5.execute(sql, params_query)

        if not contas:
            return {"success": True, "contas": [], "total": total, "page": page, "per_page": per_page}, 200

        lista = []
        for conta in contas:
            lista.append({
                "id": conta["id_metatrader_configs"],
                "id_corretora": conta["id_corretora"],
                "nome_corretora": conta["nome_fantasia"],
                "id_symbols": conta["id_symbols"],
                "server": conta["server"],
                "account": conta["account"],
                "account_number": conta["account_number"],
                "password": conta["password"],
                "status": conta["status"],
                "created_at": str(conta["created_at"]) if conta["created_at"] else None
            })

        return {
            "success": True,
            "contas": lista,
            "total": total,
            "page": page,
            "per_page": per_page
        }, 200
