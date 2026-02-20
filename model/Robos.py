from library.base.BaseModel import BaseModel

class RobosModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'robos'

    def pk(self):
        return 'id_robos'

    def fields(self):
        fields = {
                    "id_robos": 'id_robos',
                    "id_plano": 'id_plano',
                    "nome": 'nome',
                    "descricao": 'descricao',
                    "versao": 'versao',
                    "arquivo_url": 'arquivo_url',
                    "created_at": 'created_at'
                }

        return fields
