from library.base.BaseModel import BaseModel

class MetatraderConfigsLogModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'metatrader_configs_log'

    def pk(self):
        return 'id_metatrader_configs_log'

    def fields(self):
        fields = {
                    "id_metatrader_configs_log": 'id_metatrader_configs_log',
                    "id_metatrader_configs": 'id_metatrader_configs',
                    "connection_status": 'connection_status',
                    "ip": 'ip',
                    "created_at": 'created_at'
                }

        return fields
