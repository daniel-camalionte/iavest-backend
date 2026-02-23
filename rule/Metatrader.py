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

        sql = """SELECT
                    e.id_estrategia,
                    e.status AS estrategia_status,

                    mc.id_metatrader_configs,
                    mc.id_usuario,
                    mc.password AS conta_password,
                    mc.status AS conta_status,

                    (SELECT p.contrato
                     FROM assinatura a
                     INNER JOIN plano p ON p.id_plano = a.id_plano
                     WHERE a.id_usuario = mc.id_usuario AND a.status = 'active'
                     LIMIT 1) AS plano_contrato,

                    (SELECT mcl.connection_status
                     FROM metatrader_configs_log mcl
                     WHERE mcl.id_metatrader_configs = mc.id_metatrader_configs
                     ORDER BY mcl.created_at DESC
                     LIMIT 1) AS login_conta_status,

                    (SELECT mc2.account_number
                     FROM metatrader_configs mc2
                     INNER JOIN usuario u2 ON u2.id_usuario = mc2.id_usuario
                     INNER JOIN metatrader_configs_log mcl2 ON mcl2.id_metatrader_configs = mc2.id_metatrader_configs
                     WHERE u2.cpf_cnpj = u.cpf_cnpj
                     AND mcl2.connection_status = 'connected'
                     AND mcl2.created_at = (
                         SELECT MAX(mcl3.created_at)
                         FROM metatrader_configs_log mcl3
                         WHERE mcl3.id_metatrader_configs = mc2.id_metatrader_configs
                     )
                     LIMIT 1) AS login_cpf_account

                 FROM estrategia e
                 LEFT JOIN metatrader_configs mc ON mc.account_number = %s
                 LEFT JOIN usuario u ON u.id_usuario = mc.id_usuario
                 WHERE e.id_estrategia = %s
                 LIMIT 1"""

        ret = modGenerico.fetch(sql, [account_number, id_estrategia])

        # 1. Verifica se a estratégia (IA) existe
        if not ret:
            return {'msg': 'Estratégia não encontrada'}, 401

        row = ret[0]

        # 1. Verifica se a estratégia (IA) está ativa
        if row.get("estrategia_status") != 'active':
            return {'msg': 'Estratégia não está ativa'}, 401

        # 2. Verifica se tem login ativo para id_estrategia + account_number
        if row.get("login_conta_status") == 'connected':
            return {'msg': 'Já existe um login ativo para esta conta'}, 401

        # 3. Verifica se tem login ativo para id_estrategia + CPF
        if row.get("login_cpf_account"):
            return {'msg': 'Já existe um login ativo para este CPF'}, 401

        # 4. Verifica se o account_number existe no banco de dados
        if not row.get("id_metatrader_configs"):
            return {'msg': 'Conta não encontrada'}, 401

        # 5. Verifica se a conta do cliente está ativa
        if row.get("conta_status") != 'active':
            return {'msg': 'Conta do cliente não está ativa'}, 401

        # 6. Verifica se o plano do cliente está ativo
        if not row.get("plano_contrato"):
            return {'msg': 'Plano do cliente não está ativo'}, 401

        # 7. Verifica se account_number + password está correto
        if str(row.get("conta_password")) != str(password):
            return {'msg': 'Senha incorreta'}, 401

        # Registrar log de conexão
        modMetatraderConfigsLog = MetatraderConfigsLogModel()
        modMetatraderConfigsLog.save({
            "id_metatrader_configs": row.get("id_metatrader_configs"),
            "connection_status": 'connected',
            "ip": ip
        })

        return {'usuario': 1, 'id_usuario': row.get("id_usuario"), 'contrato': row.get("plano_contrato")}, 200
