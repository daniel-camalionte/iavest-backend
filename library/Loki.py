"""
Envio de logs para o Grafana Cloud Loki via HTTP push (fire-and-forget).

Uso:
    from library import Loki
    Loki.log("cerebro decidiu abrir",
             rota="/claude-trader/equalizar", op=30, direcao="compra")

Regras:
- NUNCA quebra o fluxo da aplicação: se o Loki não estiver configurado ou a
  rede falhar, o log é silenciosamente descartado.
- NÃO bloqueia o chamador: o POST roda numa thread daemon.
- Labels (indexados no Loki) sao de BAIXA cardinalidade: app, ambiente, nivel,
  rota, status. Dados de ALTA cardinalidade (account, op, ms) vao no CORPO da
  linha em formato logfmt (buscaveis via `| logfmt | account="..."`).
"""
import time
import threading

import requests

import config.env as memory

# campos que viram LABEL (baixa cardinalidade). O resto vai no corpo da linha.
_CAMPOS_LABEL = ("rota", "status")


def _enviar(payload):
    try:
        cfg = memory.loki
        requests.post(
            cfg["URL"],
            auth=(cfg["USER"], cfg["TOKEN"]),
            json=payload,
            timeout=2,
        )
    except Exception:
        pass  # monitoramento nunca derruba a aplicacao


def log(mensagem="", nivel="info", **campos):
    """Empurra 1 linha de log pro Loki, sem bloquear o chamador."""
    cfg = memory.loki
    if not cfg.get("URL") or not cfg.get("TOKEN"):
        return  # loki nao configurado -> no-op

    labels = {"app": "iavest", "ambiente": cfg.get("ENV") or "?", "nivel": nivel}
    for chave in _CAMPOS_LABEL:
        valor = campos.pop(chave, None)
        if valor is not None and valor != "":
            labels[chave] = str(valor)

    # corpo em logfmt: "mensagem k1=v1 k2=v2"
    extras = " ".join(f"{k}={v}" for k, v in campos.items() if v is not None and v != "")
    linha = (mensagem + " " + extras).strip() if extras else mensagem

    payload = {"streams": [{"stream": labels, "values": [[str(time.time_ns()), linha]]}]}
    threading.Thread(target=_enviar, args=(payload,), daemon=True).start()
