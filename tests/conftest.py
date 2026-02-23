import os
import sys
import json
from unittest.mock import MagicMock

# Guard: NUNCA rodar em produção
os.environ["FLASK_ENV"] = "test"
assert os.environ.get("FLASK_ENV") == "test", "TESTES NAO PODEM RODAR EM PRODUCAO!"

# Mock de modulos opcionais que nao sao necessarios para os testes
sys.modules["yt_dlp"] = MagicMock()

import pytest


# ============================================================
# Dados de mock reutilizaveis
# ============================================================

VALID_LOGIN_ROW = {
    "id_estrategia": 1,
    "estrategia_status": "active",
    "id_metatrader_configs": 100,
    "id_usuario": 42,
    "conta_password": "abc123",
    "conta_status": "active",
    "plano_contrato": 5,
    "login_conta_status": "disconnected",
    "login_cpf_account": None
}

VALID_ACTIVE_LOGIN_ROW = {
    "connection_status": "connected",
    "conta_password": "abc123"
}

TEST_CREDENTIALS = {
    "id_estrategia": 1,
    "account_number": 12345,
    "password": "abc123"
}

TEST_TRADE_START = {
    "account_number": 12345,
    "password": "abc123",
    "id_estrategia": 1,
    "type": "buy",
    "index_start": 128500.0,
    "contract": 1
}

TEST_TRADE_EXIT = {
    "account_number": 12345,
    "password": "abc123",
    "id_estrategia": 1,
    "index_exit": 128750.0,
    "profit_loss": 250.00
}


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="session")
def app():
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_sentry(monkeypatch):
    """Mock sentry para nunca enviar eventos reais"""
    import sentry_sdk
    monkeypatch.setattr(sentry_sdk, "set_context", lambda *a, **kw: None)
    monkeypatch.setattr(sentry_sdk, "capture_message", lambda *a, **kw: None)
    monkeypatch.setattr(sentry_sdk, "capture_exception", lambda *a, **kw: None)


# ============================================================
# Helpers para envio de requisicoes
# ============================================================

def send_payload(client, url, data):
    """Simula o formato que o MQ5 envia: payload={json} no body raw"""
    payload_str = "payload=" + json.dumps(data)
    return client.post(url, data=payload_str, content_type="text/plain")


def send_payload_form(client, url, data):
    """Simula envio via form data: payload={json}"""
    return client.post(url, data={"payload": json.dumps(data)})


def send_json(client, url, data):
    """Envio JSON padrao"""
    return client.post(url, json=data)
