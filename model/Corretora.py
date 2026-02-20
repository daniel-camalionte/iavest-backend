from library.base.BaseModel import BaseModel

class CorretoraModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'corretora'

    def pk(self):
        return 'id_corretora'

    def fields(self):
        fields = {
                    "id_corretora": 'id_corretora',
                    "razao_social": 'razao_social',
                    "nome_fantasia": 'nome_fantasia',
                    "cnpj": 'cnpj',
                    "codigo_b3": 'codigo_b3',
                    "destaque": 'destaque',
                    "ativo": 'ativo',
                    "created_at": 'created_at'
                }

        return fields
