from library.base.BaseModel import BaseModel


class SimuladorAnaliseIaModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'simulador_analise_ia'

    def pk(self):
        return 'id_analise_ia'

    def fields(self):
        return {
            "id_analise_ia":        "id_analise_ia",
            "id_ordem_cliente":     "id_ordem_cliente",
            "id_mt5_candle":        "id_mt5_candle",
            "id_intraday_analysis": "id_intraday_analysis",
            "id_market_analysis":   "id_market_analysis",
            "analise":              "analise",
            "created_at":           "created_at",
        }
