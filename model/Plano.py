from library.base.BaseModel import BaseModel

class PlanoModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'plano'

    def pk(self):
        return 'id_plano'

    def fields(self):
        fields = {
                    "id_plano": 'id_plano',
                    "nome": 'nome',
                    "descricao": 'descricao',
                    "valor_original": 'valor_original',
                    "valor_desconto": 'valor_desconto',
                    "mercadopago_plan_id": 'mercadopago_plan_id',
                    "recursos": 'recursos',
                    "destaque": 'destaque',
                    "contrato": 'contrato',
                    "esgotado": 'esgotado',
                    "ativo": 'ativo',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
