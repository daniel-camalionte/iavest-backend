from unittest.mock import patch, MagicMock
from tests.conftest import send_payload, VALID_LOGIN_ROW, VALID_ACTIVE_LOGIN_ROW


def test_fluxo_completo_login_trade_start_trade_exit(client):
    """
    Simula o fluxo real do EA MQ5:
    1. OnInit -> POST /metatrader/login (autorizar operacao)
    2. se_posicionar_comprado -> POST /metatrader/trade/start (abrir trade)
    3. zerar_posicao -> POST /metatrader/trade/exit (fechar trade com lucro)

    Todos usando formato payload= (como o MQ5 envia via WebRequest)
    """

    credentials = {
        "id_estrategia": 1,
        "account_number": 12345,
        "password": "abc123"
    }

    # === PASSO 1: Login ===
    with patch("rule.Metatrader.GenericoModel") as MockGenerico, \
         patch("rule.Metatrader.MetatraderConfigsLogModel") as MockLogModel:

        mock_generico = MockGenerico.return_value
        mock_generico.fetch.return_value = [VALID_LOGIN_ROW]

        mock_log = MockLogModel.return_value
        mock_log.save.return_value = 1

        resp_login = send_payload(client, "/metatrader/login", credentials)

        assert resp_login.status_code == 200
        login_data = resp_login.get_json()
        assert login_data["usuario"] == 1
        assert login_data["contrato"] == 5

        # Verifica que log de conexao foi registrado
        mock_log.save.assert_called_once()

    # === PASSO 2: Trade Start (compra) ===
    with patch("rule.MetatraderTrade.GenericoModel") as MockGenerico, \
         patch("rule.MetatraderTrade.TradeModel") as MockTradeModel:

        mock_generico = MockGenerico.return_value
        mock_generico.fetch.return_value = [VALID_ACTIVE_LOGIN_ROW]

        mock_trade = MockTradeModel.return_value
        mock_trade.save.return_value = 77

        trade_start_data = {
            "account_number": 12345,
            "password": "abc123",
            "id_estrategia": 1,
            "type": "buy",
            "index_start": 128500.0,
            "contract": 1
        }

        resp_start = send_payload(client, "/metatrader/trade/start", trade_start_data)

        assert resp_start.status_code == 200
        start_data = resp_start.get_json()
        assert start_data["id_trade"] == 77

        # Verifica que trade foi salvo com os dados corretos
        mock_trade.save.assert_called_once()
        save_args = mock_trade.save.call_args[0][0]
        assert save_args["type"] == "buy"
        assert save_args["index_start"] == 128500.0

    # === PASSO 3: Trade Exit (fechar com lucro) ===
    with patch("rule.MetatraderTrade.GenericoModel") as MockGenerico, \
         patch("rule.MetatraderTrade.TradeModel") as MockTradeModel:

        mock_generico = MockGenerico.return_value
        mock_generico.fetch.return_value = [VALID_ACTIVE_LOGIN_ROW]

        # close() cria 2 instancias: find e update
        mock_find = MagicMock()
        mock_find.where.return_value = mock_find
        mock_find.limit.return_value = mock_find
        mock_find.find.return_value = [{"id_trade": 77}]

        mock_update = MagicMock()
        mock_update.update.return_value = 1

        MockTradeModel.side_effect = [mock_find, mock_update]

        trade_exit_data = {
            "account_number": 12345,
            "password": "abc123",
            "id_estrategia": 1,
            "index_exit": 128750.0,
            "profit_loss": 250.00
        }

        resp_exit = send_payload(client, "/metatrader/trade/exit", trade_exit_data)

        assert resp_exit.status_code == 200
        exit_data = resp_exit.get_json()
        assert exit_data["id_trade"] == 77
        assert exit_data["operation"] == "profit"
        assert exit_data["profit_loss"] == 250.00

        # Verifica que trade foi atualizado com status closed
        mock_update.update.assert_called_once()
        update_args = mock_update.update.call_args[0][0]
        assert update_args["status"] == "closed"
        assert update_args["operation"] == "profit"
        assert update_args["index_exit"] == 128750.0
