from unittest.mock import patch, MagicMock
from tests.conftest import (
    send_payload, send_json,
    VALID_ACTIVE_LOGIN_ROW, TEST_TRADE_START, TEST_TRADE_EXIT
)

PATCH_GENERICO = "rule.MetatraderTrade.GenericoModel"
PATCH_TRADE_MODEL = "rule.MetatraderTrade.TradeModel"


def _mock_login_ativo(MockGenerico, active=True, password="abc123"):
    """Helper para configurar mock do _validar_login_ativo"""
    mock_generico = MockGenerico.return_value
    if active:
        mock_generico.fetch.return_value = [{"connection_status": "connected", "conta_password": password}]
    else:
        mock_generico.fetch.return_value = []
    return mock_generico


def _mock_trade_save(MockTradeModel, return_id=55):
    """Helper para configurar mock do TradeModel.save()"""
    mock_trade = MockTradeModel.return_value
    mock_trade.save.return_value = return_id
    return mock_trade


def _mock_trade_close(MockTradeModel, trade_found=True, update_success=True):
    """Helper para configurar mocks de find() e update() no close.
    O close() cria 2 instancias de TradeModel: uma para find, outra para update."""
    mock_find = MagicMock()
    mock_find.where.return_value = mock_find
    mock_find.limit.return_value = mock_find
    if trade_found:
        mock_find.find.return_value = [{"id_trade": 77}]
    else:
        mock_find.find.return_value = []

    mock_update = MagicMock()
    mock_update.update.return_value = 1 if update_success else 0

    MockTradeModel.side_effect = [mock_find, mock_update]
    return mock_find, mock_update


# ============================================================
# POST /metatrader/trade/start - Testes de sucesso
# ============================================================

def test_trade_start_sucesso(client):
    """Trade start com sucesso retorna id_trade"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL) as MockTradeModel:
        _mock_login_ativo(MockGenerico)
        _mock_trade_save(MockTradeModel, return_id=55)

        resp = send_json(client, "/metatrader/trade/start", TEST_TRADE_START)

        assert resp.status_code == 200
        assert resp.get_json()["id_trade"] == 55


def test_trade_start_payload_format(client):
    """Trade start usando formato payload= (como MQ5 envia)"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL) as MockTradeModel:
        _mock_login_ativo(MockGenerico)
        _mock_trade_save(MockTradeModel, return_id=55)

        resp = send_payload(client, "/metatrader/trade/start", TEST_TRADE_START)

        assert resp.status_code == 200
        assert resp.get_json()["id_trade"] == 55


# ============================================================
# POST /metatrader/trade/start - Testes de erro
# ============================================================

def test_trade_start_conta_nao_logada(client):
    """Trade start sem login ativo retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL):
        _mock_login_ativo(MockGenerico, active=False)

        resp = send_json(client, "/metatrader/trade/start", TEST_TRADE_START)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Conta não está logada"


def test_trade_start_senha_incorreta(client):
    """Trade start com senha errada retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL):
        _mock_login_ativo(MockGenerico, active=True, password="senha_correta")

        data = {**TEST_TRADE_START, "password": "senha_errada"}
        resp = send_json(client, "/metatrader/trade/start", data)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Senha incorreta"


def test_trade_start_falha_salvar(client):
    """Trade start com falha no save retorna 500"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL) as MockTradeModel:
        _mock_login_ativo(MockGenerico)
        _mock_trade_save(MockTradeModel, return_id=0)

        resp = send_json(client, "/metatrader/trade/start", TEST_TRADE_START)

        assert resp.status_code == 500
        assert resp.get_json()["msg"] == "Erro ao registrar trade"


def test_trade_start_json_invalido(client):
    """Trade start com JSON invalido retorna 422"""
    resp = client.post(
        "/metatrader/trade/start",
        data="payload={invalido",
        content_type="text/plain"
    )

    assert resp.status_code == 422
    assert "JSON" in resp.get_json()["msg"]


# ============================================================
# POST /metatrader/trade/exit - Testes de sucesso
# ============================================================

def test_trade_exit_com_lucro(client):
    """Trade exit com lucro retorna operation=profit"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL) as MockTradeModel:
        _mock_login_ativo(MockGenerico)
        _mock_trade_close(MockTradeModel)

        data = {**TEST_TRADE_EXIT, "profit_loss": 250.50}
        resp = send_json(client, "/metatrader/trade/exit", data)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["id_trade"] == 77
        assert body["operation"] == "profit"
        assert body["profit_loss"] == 250.50


def test_trade_exit_com_prejuizo(client):
    """Trade exit com prejuizo retorna operation=loss"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL) as MockTradeModel:
        _mock_login_ativo(MockGenerico)
        _mock_trade_close(MockTradeModel)

        data = {**TEST_TRADE_EXIT, "profit_loss": -50.25}
        resp = send_json(client, "/metatrader/trade/exit", data)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["operation"] == "loss"
        assert body["profit_loss"] == -50.25


def test_trade_exit_com_zero(client):
    """Trade exit com profit_loss=0 retorna operation=profit"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL) as MockTradeModel:
        _mock_login_ativo(MockGenerico)
        _mock_trade_close(MockTradeModel)

        data = {**TEST_TRADE_EXIT, "profit_loss": 0.0}
        resp = send_json(client, "/metatrader/trade/exit", data)

        assert resp.status_code == 200
        assert resp.get_json()["operation"] == "profit"


def test_trade_exit_payload_format(client):
    """Trade exit usando formato payload= (como MQ5 envia)"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL) as MockTradeModel:
        _mock_login_ativo(MockGenerico)
        _mock_trade_close(MockTradeModel)

        resp = send_payload(client, "/metatrader/trade/exit", TEST_TRADE_EXIT)

        assert resp.status_code == 200
        assert resp.get_json()["id_trade"] == 77


# ============================================================
# POST /metatrader/trade/exit - Testes de erro
# ============================================================

def test_trade_exit_conta_nao_logada(client):
    """Trade exit sem login ativo retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL):
        _mock_login_ativo(MockGenerico, active=False)

        resp = send_json(client, "/metatrader/trade/exit", TEST_TRADE_EXIT)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Conta não está logada"


def test_trade_exit_senha_incorreta(client):
    """Trade exit com senha errada retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL):
        _mock_login_ativo(MockGenerico, active=True, password="senha_correta")

        data = {**TEST_TRADE_EXIT, "password": "senha_errada"}
        resp = send_json(client, "/metatrader/trade/exit", data)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Senha incorreta"


def test_trade_exit_trade_nao_encontrado(client):
    """Trade exit sem trade aberto retorna 404"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL) as MockTradeModel:
        _mock_login_ativo(MockGenerico)
        _mock_trade_close(MockTradeModel, trade_found=False)

        resp = send_json(client, "/metatrader/trade/exit", TEST_TRADE_EXIT)

        assert resp.status_code == 404
        assert resp.get_json()["msg"] == "Trade não encontrado"


def test_trade_exit_falha_atualizar(client):
    """Trade exit com falha no update retorna 500"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_TRADE_MODEL) as MockTradeModel:
        _mock_login_ativo(MockGenerico)
        _mock_trade_close(MockTradeModel, update_success=False)

        resp = send_json(client, "/metatrader/trade/exit", TEST_TRADE_EXIT)

        assert resp.status_code == 500
        assert resp.get_json()["msg"] == "Erro ao fechar trade"
