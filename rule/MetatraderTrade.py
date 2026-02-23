from model.Trade import TradeModel
from model.Generico import GenericoModel
from datetime import datetime

class MetatraderTradeRule():

    def __init__(self):
        pass

    def _validar_login_ativo(self, account_number, password):
        modGenerico = GenericoModel()
        sql = """SELECT mcl.connection_status, mc.password AS conta_password
                 FROM metatrader_configs_log mcl
                 INNER JOIN metatrader_configs mc ON mc.id_metatrader_configs = mcl.id_metatrader_configs
                 WHERE mc.account_number = %s
                 ORDER BY mcl.created_at DESC
                 LIMIT 1"""
        ret = modGenerico.fetch(sql, [account_number])
        if not ret or ret[0].get("connection_status") != 'connected':
            return {'msg': 'Conta não está logada'}, 401
        if str(ret[0].get("conta_password")) != str(password):
            return {'msg': 'Senha incorreta'}, 401
        return None

    def create(self, data):
        account_number = data.get("account_number")
        password = data.get("password")

        erro = self._validar_login_ativo(account_number, password)
        if erro:
            return erro

        id_estrategia = data.get("id_estrategia")
        type_trade = data.get("type")
        index_start = data.get("index_start")
        contract = data.get("contract")

        modTrade = TradeModel()
        id_trade = modTrade.save({
            "account_number": account_number,
            "id_estrategia": id_estrategia,
            "type": type_trade,
            "index_start": index_start,
            "contract": contract
        })

        if not id_trade:
            return {'msg': 'Erro ao registrar trade'}, 500

        return {'id_trade': id_trade}, 200

    def close(self, data):
        account_number = data.get("account_number")
        password = data.get("password")

        erro = self._validar_login_ativo(account_number, password)
        if erro:
            return erro

        id_estrategia = data.get("id_estrategia")
        index_exit = data.get("index_exit")
        profit_loss_raw = data.get("profit_loss")

        # Converter profit_loss para float (pode vir como string ou float)
        if isinstance(profit_loss_raw, str):
            profit_loss = float(profit_loss_raw)
        else:
            profit_loss = float(profit_loss_raw) if profit_loss_raw is not None else 0.0

        # Determinar operation baseado no sinal do profit_loss
        operation = 'loss' if profit_loss < 0 else 'profit'

        # Converter index_exit para float
        index_exit = float(index_exit) if index_exit is not None else 0.0

        # Buscar trade aberto
        modTrade = TradeModel()
        dataTrade = modTrade.where(
            ['account_number', '=', account_number]
        ).where(
            ['id_estrategia', '=', id_estrategia]
        ).where(
            ['index_exit', 'IS', None]
        ).limit(1).find()

        if not dataTrade:
            return {'msg': 'Trade não encontrado'}, 404

        id_trade = dataTrade[0].get("id_trade")

        # Atualizar trade
        modTrade2 = TradeModel()
        result = modTrade2.update({
            "index_exit": index_exit,
            "status": "closed",
            "operation": operation,
            "profit_loss": round(profit_loss, 2),
            "closed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, id_trade)

        if not result:
            return {'msg': 'Erro ao fechar trade'}, 500

        return {
            'id_trade': id_trade,
            'operation': operation,
            'profit_loss': round(profit_loss, 2)
        }, 200
