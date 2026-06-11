from library.base.BaseModel import BaseModel


class FaqModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'faq'

    def pk(self):
        return 'id_faq'

    def fields(self):
        return {
            "id_faq":     "id_faq",
            "pergunta":   "pergunta",
            "resposta":   "resposta",
            "video":      "video",
            "url":        "url",
            "ordem":      "ordem",
            "ativo":      "ativo",
            "created_at": "created_at",
        }
