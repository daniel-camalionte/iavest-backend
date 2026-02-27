from library.base.BaseModel import BaseModel

class TicketModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        return 'ticket'

    def pk(self):
        return 'id_ticket'

    def fields(self):
        fields = {
                    "id_ticket": 'id_ticket',
                    "id_usuario": 'id_usuario',
                    "id_ticket_type": 'id_ticket_type',
                    "status": 'status',
                    "mensagem": 'mensagem',
                    "payload": 'payload',
                    "resolved_at": 'resolved_at',
                    "created_at": 'created_at',
                    "updated_at": 'updated_at'
                }

        return fields
