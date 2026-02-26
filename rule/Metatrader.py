from model.MetatraderConfigsLog import MetatraderConfigsLogModel
from model.Generico import GenericoModel

class MetatraderLoginRule():

    def __init__(self):
        pass

    def login(self, data, ip=None):
        id_estrategia = data.get("id_estrategia")
        account_number = data.get("account_number")
        password = data.get("password")

        modGenerico = GenericoModel()

        # 1. Validar se a estratégia existe e está ativa
        sql_estrategia = """SELECT e.id_estrategia, e.status
                            FROM estrategia e
                            WHERE e.id_estrategia = %s
                            LIMIT 1"""

        ret = modGenerico.fetch(sql_estrategia, [id_estrategia])

        if not ret:
            return {'msg': 'Estratégia não encontrada'}, 401

        if ret[0].get("status") != 'active':
            return {'msg': 'Estratégia não está ativa'}, 401

        # 2. Validar se a conta metatrader existe
        sql_conta = """SELECT mc.id_metatrader_configs, mc.id_usuario, mc.password AS conta_password, mc.status AS conta_status
                       FROM metatrader_configs mc
                       WHERE mc.account_number = %s
                       LIMIT 1"""

        ret_conta = modGenerico.fetch(sql_conta, [account_number])

        if not ret_conta:
            return {'msg': 'Conta não encontrada'}, 401

        conta = ret_conta[0]

        # 3. Validar se a conta do cliente está ativa
        if conta.get("conta_status") != 'active':
            return {'msg': 'Conta do cliente não está ativa'}, 401

        # 4. Validar se a senha está correta
        if str(conta.get("conta_password")) != str(password):
            return {'msg': 'Senha incorreta'}, 401

        # 5. Validar se o plano do cliente está ativo
        sql_plano = """SELECT p.contrato
                       FROM assinatura a
                       INNER JOIN plano p ON p.id_plano = a.id_plano
                       WHERE a.id_usuario = %s AND a.status = 'active'
                       LIMIT 1"""

        ret_plano = modGenerico.fetch(sql_plano, [conta.get("id_usuario")])

        if not ret_plano:
            return {'msg': 'Plano do cliente não está ativo'}, 401

        contrato = ret_plano[0].get("contrato")

        # Registrar log de conexão
        modMetatraderConfigsLog = MetatraderConfigsLogModel()
        modMetatraderConfigsLog.save({
            "id_metatrader_configs": conta.get("id_metatrader_configs"),
            "connection_status": 'connected',
            "ip": ip
        })

        return {'usuario': 1, 'id_usuario': conta.get("id_usuario"), 'contrato': contrato}, 200
