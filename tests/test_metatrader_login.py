from unittest.mock import patch, MagicMock
from tests.conftest import (
    send_payload, send_payload_form, send_json,
    VALID_LOGIN_ROW, TEST_CREDENTIALS
)

PATCH_GENERICO = "rule.Metatrader.GenericoModel"
PATCH_LOG_MODEL = "rule.Metatrader.MetatraderConfigsLogModel"


def _mock_login(MockGenerico, MockLogModel, row_override=None, fetch_return=None):
    """Helper para configurar mocks do login"""
    mock_generico = MockGenerico.return_value
    if fetch_return is not None:
        mock_generico.fetch.return_value = fetch_return
    else:
        row = {**VALID_LOGIN_ROW}
        if row_override:
            row.update(row_override)
        mock_generico.fetch.return_value = [row]

    mock_log = MockLogModel.return_value
    mock_log.save.return_value = 1
    return mock_generico, mock_log


# ============================================================
# Testes de sucesso
# ============================================================

def test_login_sucesso_payload_format(client):
    """Login com sucesso usando formato payload= (como o MQ5 envia)"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel)

        resp = send_payload(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["usuario"] == 1
        assert body["id_usuario"] == 42
        assert body["contrato"] == 5


def test_login_sucesso_json_format(client):
    """Login com sucesso usando JSON puro"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel)

        resp = send_json(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["usuario"] == 1


def test_login_sucesso_form_payload_format(client):
    """Login com sucesso usando form data com payload="""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel)

        resp = send_payload_form(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["usuario"] == 1


def test_login_sucesso_registra_log_conexao(client):
    """Login com sucesso deve registrar log de conexao"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _, mock_log = _mock_login(MockGenerico, MockLogModel)

        resp = send_payload(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 200
        mock_log.save.assert_called_once()
        call_args = mock_log.save.call_args[0][0]
        assert call_args["id_metatrader_configs"] == 100
        assert call_args["connection_status"] == "connected"


# ============================================================
# Testes de erro - validacoes sequenciais
# ============================================================

def test_login_estrategia_nao_encontrada(client):
    """Estrategia inexistente retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel, fetch_return=[])

        resp = send_payload(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Estratégia não encontrada"


def test_login_estrategia_inativa(client):
    """Estrategia inativa retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel, row_override={"estrategia_status": "inactive"})

        resp = send_payload(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Estratégia não está ativa"


def test_login_conta_ja_conectada(client):
    """Conta com login ativo retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel, row_override={"login_conta_status": "connected"})

        resp = send_payload(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Já existe um login ativo para esta conta"


def test_login_cpf_ja_conectado(client):
    """CPF com login ativo em outra conta retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel, row_override={"login_cpf_account": "99999"})

        resp = send_payload(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Já existe um login ativo para este CPF"


def test_login_conta_nao_encontrada(client):
    """Account number inexistente retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel, row_override={"id_metatrader_configs": None})

        resp = send_payload(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Conta não encontrada"


def test_login_conta_inativa(client):
    """Conta inativa retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel, row_override={"conta_status": "inactive"})

        resp = send_payload(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Conta do cliente não está ativa"


def test_login_plano_inativo(client):
    """Plano inativo retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel, row_override={"plano_contrato": None})

        resp = send_payload(client, "/metatrader/login", TEST_CREDENTIALS)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Plano do cliente não está ativo"


def test_login_senha_incorreta(client):
    """Senha incorreta retorna 401"""
    with patch(PATCH_GENERICO) as MockGenerico, \
         patch(PATCH_LOG_MODEL) as MockLogModel:
        _mock_login(MockGenerico, MockLogModel, row_override={"conta_password": "senha_correta"})

        data = {**TEST_CREDENTIALS, "password": "senha_errada"}
        resp = send_payload(client, "/metatrader/login", data)

        assert resp.status_code == 401
        assert resp.get_json()["msg"] == "Senha incorreta"


def test_login_json_invalido(client):
    """Body com JSON invalido retorna 422"""
    resp = client.post(
        "/metatrader/login",
        data="payload={invalido",
        content_type="text/plain"
    )

    assert resp.status_code == 422
    assert "JSON" in resp.get_json()["msg"]
