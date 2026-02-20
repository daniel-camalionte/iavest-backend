from library.base.BaseModel import BaseModel

class PagamentoModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'pagamento'

    def pk(self):
        return 'id_pagamento'

    def fields(self):
        fields = {
                    "id_pagamento": 'id_pagamento',
                    "id_assinatura": 'id_assinatura',
                    "mercadopago_payment_id": 'mercadopago_payment_id',
                    "valor": 'valor',
                    "status": 'status',
                    "status_detail": 'status_detail',
                    "metodo_pagamento": 'metodo_pagamento',
                    "data_pagamento": 'data_pagamento',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
