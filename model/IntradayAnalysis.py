from library.base.BaseModel import BaseModel


class IntradayAnalysisModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'analysis_intraday'

    def pk(self):
        return 'id_intraday_analysis'

    def fields(self):
        return {
            "id_intraday_analysis": "id_intraday_analysis",
            "id_ativos_base":       "id_ativos_base",
            "id_market_analysis":   "id_market_analysis",
            "analyzed_at":          "analyzed_at",
            "candle_datetime":      "candle_datetime",
            "candle_age_min":       "candle_age_min",
            "interval_min":         "interval_min",

            "win_price":            "win_price",
            "win_open":             "win_open",
            "win_high":             "win_high",
            "win_low":              "win_low",
            "win_volume":           "win_volume",
            "win_atr":              "win_atr",

            "ti_rsi":               "ti_rsi",
            "ti_macd":              "ti_macd",
            "ti_macd_signal":       "ti_macd_signal",
            "ti_macd_hist":         "ti_macd_hist",
            "ti_ema9":              "ti_ema9",
            "ti_ema21":             "ti_ema21",
            "ema_sinal":            "ema_sinal",
            "tf5_rsi":              "tf5_rsi",
            "tf5_macd_hist":        "tf5_macd_hist",
            "tf5_ema_sinal":        "tf5_ema_sinal",
            "tf5_alinhamento":      "tf5_alinhamento",

            "sr_resistance_1":      "sr_resistance_1",
            "sr_resistance_2":      "sr_resistance_2",
            "sr_support_1":         "sr_support_1",
            "sr_support_2":         "sr_support_2",

            "mc_vix":               "mc_vix",
            "mc_vix_level":         "mc_vix_level",
            "mc_usdbrl":            "mc_usdbrl",

            "prev_day_high":        "prev_day_high",
            "prev_day_low":         "prev_day_low",
            "prev_day_close":       "prev_day_close",
            "or_high":              "or_high",
            "or_low":               "or_low",
            "dolfut_price":         "dolfut_price",
            "dolfut_chg_pct":       "dolfut_chg_pct",
            "bova11_volume":        "bova11_volume",
            "bova11_preco":         "bova11_preco",
            "bova11_vol_rel":       "bova11_vol_rel",
            "bova11_vol_nivel":     "bova11_vol_nivel",

            "ai_direcao":           "ai_direcao",
            "direcao_operavel":     "direcao_operavel",
            "ai_forca":             "ai_forca",
            "ai_confianca":         "ai_confianca",
            "contra_tendencia":     "contra_tendencia",
            "ai_stop_loss":         "ai_stop_loss",
            "ai_alvo_1":            "ai_alvo_1",
            "ai_alvo_2":            "ai_alvo_2",
            "ai_risco_pontos":      "ai_risco_pontos",
            "ai_risco_reais":       "ai_risco_reais",
            "ai_relacao_rr":        "ai_relacao_rr",
            "ai_confluencias":      "ai_confluencias",
            "ai_riscos":            "ai_riscos",
            "ai_resumo":            "ai_resumo",
            "ai_justificativa":     "ai_justificativa",
            "resultado":            "resultado",
            "resultado_preco":      "resultado_preco",
            "resultado_at":         "resultado_at",
            "resultado_direcao":    "resultado_direcao",
            "resultado_pontos":     "resultado_pontos",
            "payload_json":         "payload_json",

            "created_at":           "created_at",
        }
