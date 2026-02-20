from library.base.BaseModel import BaseModel

class UsuarioModel(BaseModel):
    
    def __init__(self):
        super().__init__()
        pass
    
    def table(self):
        return 'usuario'
    
    def pk(self):
        return 'id_usuario'

    def fields(self):
        fields = {
                    "id_usuario": 'id_usuario',
                    "email": 'email',
                    "nome": 'nome',
                    "ddd": 'ddd',
                    "telefone": 'telefone',
                    "cpf_cnpj": 'cpf_cnpj',
                    "hash": 'hash',
                    "hash_at": 'hash_at',
                    "validacao_email": 'validacao_email',
                    "status": 'status',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields