from library.base.BaseModel import BaseModel


class ClaudeTraderModel(BaseModel):
    """Operação do Claude Trader = uma posição (equivale a 1 operação no MT5)."""

    def table(self):
        return 'claude_trader_operacao'

    def pk(self):
        return 'id_operacao'

    def fields(self):
        return {
            "id_operacao":        "id_operacao",
            "id_ativos_base":     "id_ativos_base",
            "id_market_analysis": "id_market_analysis",
            "id_intraday_origem": "id_intraday_origem",
            "account_number":     "account_number",
            "tipo_posicao":       "tipo_posicao",
            "contratos":          "contratos",
            "preco_entrada":      "preco_entrada",
            "stop_inicial":       "stop_inicial",
            "stop_loss":          "stop_loss",
            "stop_gain":          "stop_gain",
            "status":             "status",
            "acao_mt5":           "acao_mt5",
            "modo":               "modo",
            "abertura_em":        "abertura_em",
            "encerramento_em":    "encerramento_em",
            "preco_saida":        "preco_saida",
            "resultado":          "resultado",
            "resultado_pontos":   "resultado_pontos",
            "mfe_pontos":         "mfe_pontos",
            "mae_pontos":         "mae_pontos",
            "motivo":             "motivo",
            "created_at":         "created_at",
            "updated_at":         "updated_at",
        }


class ClaudeTraderAnaliseModel(BaseModel):
    """Decisões da IA (Haiku) sobre a posição aberta — a cada 15min, se no lucro.
    Registra a recomendação (manter/ajustar/encerrar) pra avaliar a estratégia depois."""

    def table(self):
        return 'claude_trader_analise'

    def pk(self):
        return 'id_analise'

    def fields(self):
        return {
            "id_analise":           "id_analise",
            "id_operacao":          "id_operacao",
            "id_intraday_analysis": "id_intraday_analysis",
            "preco_no_momento":     "preco_no_momento",
            "lucro_pontos":         "lucro_pontos",
            "recomendacao":         "recomendacao",
            "stop_antes":           "stop_antes",
            "stop_sugerido":        "stop_sugerido",
            "acatado":              "acatado",
            "motivo":               "motivo",
            "analise_json":         "analise_json",
            "ia_disponivel":        "ia_disponivel",
            "created_at":           "created_at",
        }


class ClaudeTraderLogModel(BaseModel):
    """Auditoria de cada decisão/movimento de stop do Claude Trader."""

    def table(self):
        return 'claude_trader_log'

    def pk(self):
        return 'id_log'

    def fields(self):
        return {
            "id_log":       "id_log",
            "id_operacao":  "id_operacao",
            "evento":       "evento",
            "fonte":        "fonte",
            "preco_evento": "preco_evento",
            "stop_antes":   "stop_antes",
            "stop_depois":  "stop_depois",
            "motivo":       "motivo",
            "created_at":   "created_at",
        }
