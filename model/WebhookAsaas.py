from library.base.BaseModel import BaseModel

class WebhookAsaasModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'webhook_asaas'

    def pk(self):
        return 'id_webhook'

    def fields(self):
        fields = {
                    "id_webhook": 'id_webhook',
                    "event": 'event',
                    "payload": 'payload',
                    "response": 'response',
                    "status": 'status',
                    "erro": 'erro',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
