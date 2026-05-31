from library.base.BaseModel import BaseModel


class TermoAceiteModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'termo_aceite'

    def pk(self):
        return 'id_termo_aceite'

    def fields(self):
        return {
            "id_termo_aceite": "id_termo_aceite",
            "id_usuario":      "id_usuario",
            "tipo_aceite":     "tipo_aceite",
            "termo_versao":    "termo_versao",
            "aceito_em":       "aceito_em",
            "ip_address":      "ip_address",
            "user_agent":      "user_agent",
            "created_at":      "created_at",
        }
