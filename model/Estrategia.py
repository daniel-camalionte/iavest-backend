from library.base.BaseModel import BaseModel

class EstrategiaModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'estrategia'

    def pk(self):
        return 'id_estrategia'

    def fields(self):
        fields = {
                    "id_estrategia": 'id_estrategia',
                    "nome": 'nome',
                    "descricao": 'descricao',
                    "type": 'type',
                    "risco": 'risco',
                    "status": 'status',
                    "parametros": 'parametros',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
