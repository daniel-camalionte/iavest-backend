from library.base.BaseModel import BaseModel

class PlanoUsuarioModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'plano_usuario'

    def pk(self):
        return 'id_plano_usario'

    def fields(self):
        fields = {
                    "id_plano_usario": 'id_plano_usario',
                    "id_plano": 'id_plano',
                    "id_usuario": 'id_usuario',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
