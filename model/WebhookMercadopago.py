from library.base.BaseModel import BaseModel

class WebhookMercadopagoModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'webhook_mercadopago'

    def pk(self):
        return 'id_webhook'

    def fields(self):
        fields = {
                    "id_webhook": 'id_webhook',
                    "action": 'action',
                    "payload": 'payload',
                    "response": 'response',
                    "status": 'status',
                    "attempts": 'attempts',
                    "erro": 'erro',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
