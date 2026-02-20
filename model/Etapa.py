from library.base.BaseModel import BaseModel

class EtapaModel(BaseModel):

    def table(self):
        return 'etapa'

    def pk(self):
        return 'id_etapa'

    def fields(self):
        fields = {
                    "id_etapa": 'id_etapa',
                    "ordem": 'ordem',
                    "titulo": 'titulo',
                    "descricao": 'descricao',
                    "url": 'url',
                    "video": 'video',
                    "created_at": 'created_at'
                }

        return fields
