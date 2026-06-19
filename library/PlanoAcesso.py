"""Validação de acesso a features por plano (assinatura ativa).

Genérico e reutilizável: cada feature passa sua própria lista de planos liberados
(normalmente vinda do config/env.py). Padrão do produto: features premium são
liberadas apenas para os planos premium configurados no .env.
"""
from library.MySql import MySql


def verificar_acesso(id_cliente, planos_permitidos):
    """True se o cliente tem assinatura ATIVA (status='active') em algum dos planos."""
    if not id_cliente or not planos_permitidos:
        return False
    ph = ",".join(["%s"] * len(planos_permitidos))
    rows = MySql().fetch(
        "SELECT id_plano FROM assinatura "
        "WHERE id_usuario=%s AND status='active' AND id_plano IN (" + ph + ") LIMIT 1",
        tuple([id_cliente] + list(planos_permitidos))
    ) or []
    return bool(rows)


def nomes_planos(planos):
    """Nomes ÚNICOS dos planos (para texto de upsell), preservando a ordem.
    Planos diferentes podem ter o mesmo nome (ex: 3 e 7 = 'Plano Premium')."""
    if not planos:
        return []
    ph = ",".join(["%s"] * len(planos))
    rows = MySql().fetch(
        "SELECT nome FROM plano WHERE id_plano IN (" + ph + ") ORDER BY id_plano",
        tuple(planos)
    ) or []
    out = []
    for r in rows:
        n = r.get("nome")
        if n and n not in out:
            out.append(n)
    return out
