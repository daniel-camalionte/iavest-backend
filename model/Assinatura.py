from library.base.BaseModel import BaseModel

class AssinaturaModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'assinatura'

    def pk(self):
        return 'id_assinatura'

    def fields(self):
        fields = {
                    "id_assinatura": 'id_assinatura',
                    "id_usuario": 'id_usuario',
                    "id_plano": 'id_plano',
                    "mercadopago_subscription_id": 'mercadopago_subscription_id',
                    "checkout_url": 'checkout_url',
                    "status": 'status',
                    "data_inicio": 'data_inicio',
                    "data_fim": 'data_fim',
                    "data_proxima_cobranca": 'data_proxima_cobranca',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
