from library.base.BaseModel import BaseModel

class TicketTypeModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'ticket_type'

    def pk(self):
        return 'id_ticket_type'

    def fields(self):
        fields = {
                    "id_ticket_type": 'id_ticket_type',
                    "identificador": 'identificador',
                    "label": 'label',
                    "descricao": 'descricao',
                    "ativo": 'ativo',
                    "ordem": 'ordem',
                    "created_at": 'created_at'
                }

        return fields
