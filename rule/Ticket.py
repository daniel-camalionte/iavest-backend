from model.Ticket import TicketModel
from model.TicketType import TicketTypeModel
from model.Usuario import UsuarioModel
from model.Assinatura import AssinaturaModel
from model.Plano import PlanoModel
from library.SMTP import SMTP
import config.env as memory
import json
from datetime import datetime

class TicketRule():

    def listar(self, id_usuario):
        modTicket = TicketModel()
        tickets = modTicket.where(['id_usuario', '=', id_usuario]).order('created_at', 'DESC').find()

        if not tickets:
            return {"success": True, "tickets": []}, 200

        lista = []
        for ticket in tickets:
            lista.append({
                "id_ticket": ticket["id_ticket"],
                "id_usuario": ticket["id_usuario"],
                "id_ticket_type": ticket["id_ticket_type"],
                "status": ticket["status"],
                "mensagem": ticket["mensagem"],
                "payload": ticket["payload"],
                "resolved_at": str(ticket["resolved_at"]) if ticket.get("resolved_at") else None,
                "created_at": str(ticket["created_at"]) if ticket.get("created_at") else None,
                "updated_at": str(ticket["updated_at"]) if ticket.get("updated_at") else None
            })

        return {"success": True, "tickets": lista}, 200

    def criar(self, id_usuario, data):
        id_ticket_type = data.get("id_ticket_type")
        titulo = data.get("titulo")
        descricao = data.get("descricao")

        if not id_ticket_type or not titulo or not descricao:
            return {"success": False, "message": "Campos obrigatórios: id_ticket_type, titulo, descricao"}, 400

        # Buscar dados do usuário
        modUsuario = UsuarioModel()
        usuario_data = modUsuario.find_one(id_usuario)
        if not usuario_data:
            return {"success": False, "message": "Usuário não encontrado"}, 400
        usuario = usuario_data[0]

        # Buscar assinatura ativa
        modAssinatura = AssinaturaModel()
        assinatura_data = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).find()
        tem_assinatura = bool(assinatura_data)
        plano_nome = None
        if tem_assinatura:
            modPlano = PlanoModel()
            plano_data = modPlano.find_one(assinatura_data[0]["id_plano"])
            if plano_data:
                plano_nome = plano_data[0].get("nome")

        # Buscar ticket type
        modTicketType = TicketTypeModel()
        ticket_type_data = modTicketType.find_one(id_ticket_type)
        if not ticket_type_data:
            return {"success": False, "message": "Tipo de ticket inválido"}, 400
        ticket_type = ticket_type_data[0]

        # Enviar e-mail
        agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        self._enviar_email(usuario, tem_assinatura, plano_nome, ticket_type, data, agora)

        # Insert no banco
        obj = {
            "id_usuario": id_usuario,
            "id_ticket_type": id_ticket_type,
            "payload": json.dumps(data, ensure_ascii=False)
        }

        modTicket = TicketModel()
        id_ticket = modTicket.save(obj)

        if not id_ticket:
            return {"success": False, "message": "Erro ao registrar ticket"}, 500

        return {"success": True, "message": "Ticket registrado com sucesso"}, 201

    def _enviar_email(self, usuario, tem_assinatura, plano_nome, ticket_type, data, agora):
        titulo = data.get("titulo", "")
        descricao = data.get("descricao", "")
        assinatura_str = f'Sim — {plano_nome}' if tem_assinatura and plano_nome else ('Sim' if tem_assinatura else 'Não')
        telefone = f'({usuario.get("ddd", "")}) {usuario.get("telefone", "")}' if usuario.get("telefone") else '—'

        body = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 8px;">Novo Ticket de Suporte — IAvest</h2>

    <h3 style="color: #555;">Dados do Usuário</h3>
    <table style="border-collapse: collapse; width: 100%;">
        <tr><td style="padding: 6px 12px 6px 0;"><b>Nome:</b></td><td style="padding: 6px 0;">{usuario.get("nome", "—")}</td></tr>
        <tr><td style="padding: 6px 12px 6px 0;"><b>E-mail:</b></td><td style="padding: 6px 0;">{usuario.get("email", "—")}</td></tr>
        <tr><td style="padding: 6px 12px 6px 0;"><b>Telefone:</b></td><td style="padding: 6px 0;">{telefone}</td></tr>
        <tr><td style="padding: 6px 12px 6px 0;"><b>Assinatura ativa:</b></td><td style="padding: 6px 0;">{assinatura_str}</td></tr>
    </table>

    <h3 style="color: #555; margin-top: 24px;">Dados do Ticket</h3>
    <table style="border-collapse: collapse; width: 100%;">
        <tr><td style="padding: 6px 12px 6px 0;"><b>Tipo:</b></td><td style="padding: 6px 0;">{ticket_type.get("label", "—")}</td></tr>
        <tr><td style="padding: 6px 12px 6px 0;"><b>Categoria:</b></td><td style="padding: 6px 0;">{ticket_type.get("descricao", "—")}</td></tr>
        <tr><td style="padding: 6px 12px 6px 0;"><b>Título:</b></td><td style="padding: 6px 0;">{titulo}</td></tr>
        <tr><td style="padding: 6px 12px 6px 0; vertical-align: top;"><b>Descrição:</b></td><td style="padding: 6px 0;">{descricao}</td></tr>
        <tr><td style="padding: 6px 12px 6px 0;"><b>Data/Hora:</b></td><td style="padding: 6px 0;">{agora}</td></tr>
    </table>

    <hr style="margin-top: 32px; border: none; border-top: 1px solid #ddd;">
    <small style="color: #999;">IAvest — Sistema de Suporte Interno</small>
</body>
</html>
"""

        assunto = f"[Suporte IAvest] {ticket_type.get('label', 'Ticket')} — {titulo}"
        emails = [e.strip() for e in memory.ticket["SUPPORT_EMAILS"].split(",") if e.strip()]
        smtp = SMTP()
        for email in emails:
            smtp.send(email, assunto, body)
