from library.base.BaseModel import BaseModel

class SymbolsModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'symbols'

    def pk(self):
        return 'id_symbols'

    def fields(self):
        fields = {
                    "id_symbols": 'id_symbols',
                    "type": 'type',
                    "ticker": 'ticker',
                    "ativo": 'ativo',
                    "created_at": 'created_at'
                }

        return fields
