from library.base.BaseModel import BaseModel

class MetatraderConfigsModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'metatrader_configs'

    def pk(self):
        return 'id_metatrader_configs'

    def fields(self):
        fields = {
                    "id_metatrader_configs": 'id_metatrader_configs',
                    "id_usuario": 'id_usuario',
                    "id_corretora": 'id_corretora',
                    "id_symbols": 'id_symbols',
                    "account": 'account',
                    "account_number": 'account_number',
                    "password": 'password',
                    "platform": 'platform',
                    "status": 'status',
                    "settings": 'settings',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
