from library.base.BaseModel import BaseModel


class IntradayHealthLogModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'intraday_health_log'

    def pk(self):
        return 'id_health_log'

    def fields(self):
        return {
            "id_health_log":       "id_health_log",
            "checked_at":          "checked_at",
            "id_ativos_base":      "id_ativos_base",
            "status":              "status",
            "pregao_aberto":       "pregao_aberto",
            "falhas":              "falhas",
            "fundamental_ok":      "fundamental_ok",
            "mt5_ultimo_candle":   "mt5_ultimo_candle",
            "mt5_atraso_min":      "mt5_atraso_min",
            "ultimo_sinal_at":     "ultimo_sinal_at",
            "ultimo_sinal_ha_min": "ultimo_sinal_ha_min",
            "pendencias_qtd":      "pendencias_qtd",
            "sinais_hoje_qtd":     "sinais_hoje_qtd",
            "detalhe_json":        "detalhe_json",
            "created_at":          "created_at",
        }
