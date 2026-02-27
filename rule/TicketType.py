from model.TicketType import TicketTypeModel

class TicketTypeRule():

    def listar(self):
        modTicketType = TicketTypeModel()
        tipos = modTicketType.where(['ativo', '=', 1]).order('ordem', 'ASC').find()

        if not tipos:
            return {"success": True, "types": []}, 200

        lista = []
        for tipo in tipos:
            lista.append({
                "id_ticket_type": tipo["id_ticket_type"],
                "label": tipo["label"],
                "descricao": tipo["descricao"],
                "ordem": tipo["ordem"]
            })

        return {"success": True, "types": lista}, 200
