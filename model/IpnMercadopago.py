from library.base.BaseModel import BaseModel

class IpnMercadopagoModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'ipn_mercadopago'

    def pk(self):
        return 'id_ipn'

    def fields(self):
        fields = {
                    "id_ipn": 'id_ipn',
                    "topic": 'topic',
                    "resource_id": 'resource_id',
                    "status": 'status',
                    "payload": 'payload',
                    "erro": 'erro',
                    "created_at": 'created_at',
                    "processed_at": 'processed_at'
                }

        return fields
