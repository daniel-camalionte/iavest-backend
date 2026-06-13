from library.base.BaseModel import BaseModel


class MarketAnalysisModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'analysis_market'

    def pk(self):
        return 'id_market_analysis'

    def fields(self):
        return {
            "id_market_analysis":  "id_market_analysis",
            "id_ativos_base":      "id_ativos_base",
            "analyzed_at":         "analyzed_at",

            "recommendation":      "recommendation",
            "confidence":          "confidence",
            "contracts":           "contracts",
            "ia_buy":              "ia_buy",
            "ia_sell":             "ia_sell",

            "score_total":         "score_total",
            "score_technical":     "score_technical",
            "score_macro":         "score_macro",

            "sig_sma9":            "sig_sma9",
            "sig_sma21":           "sig_sma21",
            "sig_sma50":           "sig_sma50",
            "sig_ema_cross":       "sig_ema_cross",
            "sig_rsi":             "sig_rsi",
            "sig_macd":            "sig_macd",
            "sig_bbands":          "sig_bbands",
            "sig_adx":             "sig_adx",
            "sig_obv":             "sig_obv",

            "ctx_opening_gap":     "ctx_opening_gap",
            "ctx_consecutive_days": "ctx_consecutive_days",
            "ctx_momentum":        "ctx_momentum",

            "msig_spy":            "msig_spy",
            "msig_qqq":            "msig_qqq",
            "msig_dia":            "msig_dia",
            "msig_es1":            "msig_es1",
            "msig_nq1":            "msig_nq1",
            "msig_uso":            "msig_uso",
            "msig_vxx":            "msig_vxx",
            "msig_usdbrl":         "msig_usdbrl",
            "msig_dxy":            "msig_dxy",
            "msig_ewz":            "msig_ewz",
            "msig_pbr":            "msig_pbr",
            "msig_vale":           "msig_vale",

            "ap_trigger":          "ap_trigger",
            "ap_buy_trigger":      "ap_buy_trigger",
            "ap_sell_trigger":     "ap_sell_trigger",
            "ap_description":      "ap_description",

            "td_price":            "td_price",
            "td_prev_close":       "td_prev_close",
            "td_prev_high":        "td_prev_high",
            "td_prev_low":         "td_prev_low",
            "td_opening_gap_pct":  "td_opening_gap_pct",
            "td_consecutive_days": "td_consecutive_days",
            "td_volume":           "td_volume",
            "td_obv":              "td_obv",
            "td_sma9":             "td_sma9",
            "td_sma21":            "td_sma21",
            "td_sma50":            "td_sma50",
            "td_sma200":           "td_sma200",
            "td_ema9":             "td_ema9",
            "td_ema21":            "td_ema21",
            "td_rsi":              "td_rsi",
            "td_macd":             "td_macd",
            "td_macd_signal":      "td_macd_signal",
            "td_macd_histogram":   "td_macd_histogram",
            "td_bb_upper":         "td_bb_upper",
            "td_bb_middle":        "td_bb_middle",
            "td_bb_lower":         "td_bb_lower",
            "td_adx":              "td_adx",
            "td_plus_di":          "td_plus_di",
            "td_minus_di":         "td_minus_di",

            "mc_spy_price":        "mc_spy_price",
            "mc_spy_pct":          "mc_spy_pct",
            "mc_qqq_price":        "mc_qqq_price",
            "mc_qqq_pct":          "mc_qqq_pct",
            "mc_dia_price":        "mc_dia_price",
            "mc_dia_pct":          "mc_dia_pct",
            "mc_es1_price":        "mc_es1_price",
            "mc_es1_pct":          "mc_es1_pct",
            "mc_nq1_price":        "mc_nq1_price",
            "mc_nq1_pct":          "mc_nq1_pct",
            "mc_uso_price":        "mc_uso_price",
            "mc_uso_pct":          "mc_uso_pct",
            "mc_vxx_price":        "mc_vxx_price",
            "mc_vxx_pct":          "mc_vxx_pct",
            "mc_vxx_level":        "mc_vxx_level",
            "mc_usdbrl_price":     "mc_usdbrl_price",
            "mc_usdbrl_pct":       "mc_usdbrl_pct",
            "mc_dxy_price":        "mc_dxy_price",
            "mc_dxy_pct":          "mc_dxy_pct",
            "mc_ewz_price":        "mc_ewz_price",
            "mc_ewz_pct":          "mc_ewz_pct",
            "mc_pbr_price":        "mc_pbr_price",
            "mc_pbr_pct":          "mc_pbr_pct",
            "mc_vale_price":       "mc_vale_price",
            "mc_vale_pct":         "mc_vale_pct",

            "blind_spots":         "blind_spots",
            "daytrade_scenarios":  "daytrade_scenarios",
            "narrative":           "narrative",
            "payload_json":        "payload_json",

            "created_at":          "created_at",
        }
