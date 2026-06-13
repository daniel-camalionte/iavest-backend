from library.base.BaseModel import BaseModel


class IntradayORModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'analysis_intraday_or'

    def pk(self):
        return 'id_intraday_or'

    def fields(self):
        return {
            "id_intraday_or": "id_intraday_or",
            "id_ativos_base": "id_ativos_base",
            "data":           "data",
            "or_high":        "or_high",
            "or_low":         "or_low",
            "created_at":     "created_at",
        }
