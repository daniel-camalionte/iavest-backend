from library.base.BaseModel import BaseModel


class Mt5CandlesModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'mt5_candles'

    def pk(self):
        return 'id_mt5_candle'

    def fields(self):
        return {
            "id_mt5_candle": "id_mt5_candle",
            "id_symbols":    "id_symbols",
            "datetime":      "datetime",
            "open":          "open",
            "high":          "high",
            "low":           "low",
            "close":         "close",
            "tick_vol":      "tick_vol",
            "vol":           "vol",
            "spread":        "spread",
        }
