from library.base.BaseModel import BaseModel

class TradeModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'trade'

    def pk(self):
        return 'id_trade'

    def fields(self):
        fields = {
                    "id_trade": 'id_trade',
                    "account_number": 'account_number',
                    "id_estrategia": 'id_estrategia',
                    "type": 'type',
                    "index_start": 'index_start',
                    "index_exit": 'index_exit',
                    "contract": 'contract',
                    "status": 'status',
                    "operation": 'operation',
                    "profit_loss": 'profit_loss',
                    "closed_at": 'closed_at',
                    "notes": 'notes',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
