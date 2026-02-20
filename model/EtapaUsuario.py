from library.base.BaseModel import BaseModel

class EtapaUsuarioModel(BaseModel):

    def table(self):
        return 'etapa_usuario'

    def pk(self):
        return 'id_etapa_usuario'

    def fields(self):
        fields = {
                    "id_etapa_usuario": 'id_etapa_usuario',
                    "id_etapa": 'id_etapa',
                    "id_usuario": 'id_usuario',
                    "created_at": 'created_at'
                }

        return fields
