from library.base.BaseModel import BaseModel

class PlanoEstrategiaModel(BaseModel):

    def table(self):
        return 'plano_estrategia'

    def pk(self):
        return 'id_plano_estrategia'

    def fields(self):
        fields = {
                    "id_plano_estrategia": 'id_plano_estrategia',
                    "id_plano": 'id_plano',
                    "id_estrategia": 'id_estrategia'
                }

        return fields
