from library.MySql import MySql

PONTO_REAIS = 0.20  # R$ por ponto por contrato (WIN)


class IntradayResumoRule:
    """Resumo agregado dos sinais intraday de um dia (por id_market_analysis).

    Calculado on-demand a partir do analysis_intraday — fonte única de verdade.
    O front NÃO calcula nada: só exibe o que vem daqui.
    """

    @staticmethod
    def resumo(id_market_analysis):
        if not id_market_analysis:
            return {"error": "Parâmetro 'id_market_analysis' é obrigatório"}, 400

        row = MySql().fetch(
            "SELECT "
            "  COUNT(*) AS total, "
            "  SUM(ai_direcao = 'neutro') AS neutro, "
            "  SUM(resultado IN ('alvo_1_atingido','alvo_2_atingido')) AS alvo, "
            "  SUM(resultado = 'stop_atingido') AS stop_cnt, "
            "  SUM(resultado = 'expirado') AS expirado, "
            "  SUM(resultado IS NULL AND ai_direcao <> 'neutro') AS pendente, "
            "  SUM(resultado_direcao = 'favor') AS favor, "
            "  SUM(resultado_direcao = 'contra') AS contra, "
            "  SUM(CASE WHEN resultado_pontos > 0 THEN resultado_pontos ELSE 0 END) AS ganhos, "
            "  SUM(CASE WHEN resultado_pontos < 0 THEN resultado_pontos ELSE 0 END) AS perdas, "
            "  SUM(resultado_pontos) AS net, "
            "  MAX(resultado_pontos) AS maior_ganho, "
            "  MIN(resultado_pontos) AS maior_perda "
            "FROM analysis_intraday "
            "WHERE id_market_analysis = %s",
            (id_market_analysis,)
        )

        r = row[0] if row else {}
        if not r or not r.get("total"):
            return {
                "id_market_analysis": id_market_analysis,
                "total_sinais": 0,
                "resumo": None,
                "msg": "Nenhum sinal intraday para este id_market_analysis",
            }, 200

        def _i(v):  # SUM volta como Decimal/None
            return int(v) if v is not None else 0

        favor   = _i(r.get("favor"))
        contra  = _i(r.get("contra"))
        direc   = favor + contra
        ganhos  = _i(r.get("ganhos"))
        perdas  = _i(r.get("perdas"))          # negativo
        net     = _i(r.get("net"))

        taxa_acerto   = round(100 * favor / direc) if direc else None
        profit_factor = round(ganhos / abs(perdas), 2) if perdas else (None if ganhos == 0 else 999)

        return {
            "id_market_analysis": id_market_analysis,
            "total_sinais": _i(r.get("total")),
            "pendentes":    _i(r.get("pendente")),
            "resumo": {
                # contagens por tipo de resultado
                "neutro":    _i(r.get("neutro")),
                "alvo":      _i(r.get("alvo")),
                "stop":      _i(r.get("stop_cnt")),
                "expirado":  _i(r.get("expirado")),
                # direção (trades resolvidos)
                "direcionais": direc,
                "acerto":      favor,
                "erro":        contra,
                "taxa_acerto": taxa_acerto,          # % favor / direcionais
                # pontos (P&L exit-based)
                "ganhos_pts":    ganhos,
                "perdas_pts":    perdas,
                "net_pts":       net,
                "net_reais":     round(net * PONTO_REAIS, 2),
                "profit_factor": profit_factor,      # ganhos / |perdas|
                "maior_ganho_pts": _i(r.get("maior_ganho")),
                "maior_perda_pts": _i(r.get("maior_perda")),
            },
        }, 200
