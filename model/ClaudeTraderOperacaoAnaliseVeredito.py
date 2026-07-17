from library.base.BaseModel import BaseModel


class ClaudeTraderOperacaoAnaliseVeredictoModel(BaseModel):
    """Parecer do analisador (Claude Haiku) sobre uma proposta da fila. 1 linha por
    analise. Hibrido: campos estruturados (pra calibrar/agregar) + analise_json cru
    (pra self-review generativo). Link: id_operacao_analise -> claude_trader_operacao_analise.
    """

    def table(self):
        return 'claude_trader_operacao_analise_veredito'

    def pk(self):
        return 'id_veredito'

    def fields(self):
        return {
            "id_veredito":             "id_veredito",
            "id_operacao_analise":     "id_operacao_analise",
            "veredito":                "veredito",
            "regra":                   "regra",
            "confianca":               "confianca",
            "fundamentalista_direcao": "fundamentalista_direcao",
            "intraday_direcao":        "intraday_direcao",
            "id_market_analysis":      "id_market_analysis",
            "id_intraday_origem":      "id_intraday_origem",
            "motivo":                  "motivo",
            "analise_json":            "analise_json",
            "toggle_enforcado":        "toggle_enforcado",
            "created_at":              "created_at",
        }
