from model.Assinatura import AssinaturaModel
from model.Plano import PlanoModel
from model.Usuario import UsuarioModel
from library.HttpClient import HttpClient
import config.env as memory
from datetime import datetime, timedelta

class AssinaturaAsaasRule():

    def __init__(self):
        pass

    def criar(self, id_usuario, data, remote_ip):
        plano_id = data.get("plano_id")

        modPlano = PlanoModel()
        plano_data = modPlano.find_one(plano_id)

        if not plano_data:
            return {"success": False, "message": "Plano inválido"}, 400

        plano = plano_data[0]

        if not plano.get("ativo"):
            return {"success": False, "message": "Plano inválido"}, 400

        modAssinatura = AssinaturaModel()
        assinatura_ativa = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).find()

        if assinatura_ativa:
            return {"success": False, "message": "Usuário já possui assinatura ativa"}, 409

        # Reutilizar assinatura pendente existente apenas se for do mesmo plano
        assinatura_pendente = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'pending']).where(['gateway', '=', 'asaas']).find()

        if assinatura_pendente:
            ass = assinatura_pendente[0]
            if str(ass.get("id_plano")) == str(plano_id):
                invoice_url = ass.get("checkout_url") or self._buscar_invoice_url(ass.get("asaas_subscription_id", ""))
                return {"success": True, "invoice_url": invoice_url}, 200
            else:
                # Plano diferente: cancela a assinatura pendente anterior no Asaas e no banco
                sub_id = ass.get("asaas_subscription_id")
                if sub_id:
                    self._cancelar_assinatura(sub_id)
                modAssinatura.update({
                    "status": "cancelled",
                    "data_fim": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }, ass["id_assinatura"])

        modUsuario = UsuarioModel()
        usuario_data = modUsuario.find_one(id_usuario)

        if not usuario_data:
            return {"success": False, "message": "Usuário não encontrado"}, 400

        usuario = usuario_data[0]

        customer_id, error = self._criar_ou_buscar_cliente(usuario)

        if not customer_id:
            return {"success": False, "message": "Erro ao criar cliente no Asaas", "detail": error}, 500

        sub_response, sub_error = self._criar_assinatura(customer_id, plano, id_usuario)

        if not sub_response:
            return {"success": False, "message": "Erro ao criar assinatura no Asaas", "detail": sub_error}, 500

        invoice_url = self._buscar_invoice_url(sub_response.get("id", ""))

        now = datetime.now()
        proxima = now + timedelta(days=30)

        obj = {
            "id_usuario": id_usuario,
            "id_plano": plano_id,
            "asaas_customer_id": customer_id,
            "asaas_subscription_id": sub_response.get("id", ""),
            "gateway": "asaas",
            "checkout_url": invoice_url,
            "remote_ip": remote_ip,
            "status": "pending",
            "data_inicio": now.strftime('%Y-%m-%d %H:%M:%S'),
            "data_proxima_cobranca": proxima.strftime('%Y-%m-%d %H:%M:%S')
        }

        modAssinatura.save(obj)

        return {"success": True, "invoice_url": invoice_url}, 201

    def invoice(self, id_usuario):
        modAssinatura = AssinaturaModel()
        assinatura = modAssinatura \
            .where(['id_usuario', '=', id_usuario]) \
            .where(['gateway', '=', 'asaas']) \
            .find()

        if not assinatura:
            return {"success": False, "message": "Nenhuma assinatura Asaas encontrada"}, 404

        ass = assinatura[0]

        if ass.get("status") == "active":
            return {"success": False, "message": "Assinatura já está ativa"}, 409

        subscription_id = ass.get("asaas_subscription_id")
        if not subscription_id:
            return {"success": False, "message": "ID de assinatura não encontrado"}, 404

        headers = {"access_token": memory.asaas["API_KEY"]}

        resp = HttpClient.get(
            memory.asaas["API_URL"] + "/subscriptions/" + subscription_id + "/payments?status=PENDING,OVERDUE",
            headers=headers
        )

        if not resp or resp["status_code"] != 200:
            return {"success": False, "message": "Erro ao consultar cobranças no Asaas"}, 500

        pagamentos = resp["data"].get("data", [])

        if not pagamentos:
            return {"success": False, "message": "Nenhuma cobrança pendente encontrada"}, 404

        # Pega a mais recente (primeira da lista — Asaas retorna em ordem decrescente de vencimento)
        pagamento = pagamentos[0]
        invoice_url = pagamento.get("invoiceUrl", "")

        if not invoice_url:
            return {"success": False, "message": "URL de pagamento não disponível"}, 404

        return {
            "success": True,
            "invoice_url": invoice_url,
            "vencimento": pagamento.get("dueDate"),
            "valor": pagamento.get("value"),
            "status": pagamento.get("status")
        }, 200

    def cancelar(self, id_usuario):
        modAssinatura = AssinaturaModel()
        assinatura = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).where(['gateway', '=', 'asaas']).find()

        if not assinatura:
            assinatura = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'pending']).where(['gateway', '=', 'asaas']).find()

        if not assinatura:
            return {"success": False, "message": "Nenhuma assinatura ativa encontrada"}, 404

        ass = assinatura[0]

        sub_id = ass.get("asaas_subscription_id")
        if sub_id:
            self._cancelar_assinatura(sub_id)

        modAssinatura.update({
            "status": "cancelled",
            "data_fim": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, ass["id_assinatura"])

        return {"success": True, "message": "Assinatura cancelada com sucesso"}, 200

    def _criar_ou_buscar_cliente(self, usuario):
        cpf = usuario.get("cpf_cnpj", "")
        headers = {
            "access_token": memory.asaas["API_KEY"],
            "Content-Type": "application/json"
        }

        if cpf:
            cpf_limpo = ''.join(filter(str.isdigit, cpf))
            resp = HttpClient.get(
                memory.asaas["API_URL"] + "/customers?cpfCnpj=" + cpf_limpo,
                headers=headers
            )
            if resp and resp["status_code"] == 200:
                customers = resp["data"].get("data", [])
                if customers:
                    return customers[0]["id"], None

        payload = {
            "name": usuario.get("nome", ""),
            "email": usuario.get("email", ""),
            "cpfCnpj": ''.join(filter(str.isdigit, cpf)) if cpf else ""
        }

        resp = HttpClient.post(memory.asaas["API_URL"] + "/customers", headers=headers, payload=payload)

        if resp and resp["status_code"] in [200, 201]:
            return resp["data"]["id"], None

        return None, str(resp["data"] if resp else "Sem resposta")

    def _criar_assinatura(self, customer_id, plano, id_usuario):
        headers = {
            "access_token": memory.asaas["API_KEY"],
            "Content-Type": "application/json"
        }

        payload = {
            "customer": customer_id,
            "billingType": "UNDEFINED",
            "nextDueDate": datetime.now().strftime('%Y-%m-%d'),
            "value": float(plano["valor_original"]),
            "cycle": "MONTHLY",
            "description": plano["nome"] + " - IAvest",
            "externalReference": str(id_usuario)
        }

        resp = HttpClient.post(memory.asaas["API_URL"] + "/subscriptions", headers=headers, payload=payload)

        if resp and resp["status_code"] in [200, 201]:
            return resp["data"], None

        return None, str(resp["data"] if resp else "Sem resposta")

    def _buscar_invoice_url(self, subscription_id):
        headers = {"access_token": memory.asaas["API_KEY"]}

        # Tenta buscar invoiceUrl direto da assinatura
        resp_sub = HttpClient.get(
            memory.asaas["API_URL"] + "/subscriptions/" + subscription_id,
            headers=headers
        )
        if resp_sub and resp_sub["status_code"] == 200:
            url = resp_sub["data"].get("invoiceUrl", "")
            if url:
                return url

        # Tenta buscar via primeira cobrança
        resp = HttpClient.get(
            memory.asaas["API_URL"] + "/subscriptions/" + subscription_id + "/payments",
            headers=headers
        )

        if not resp or resp["status_code"] != 200:
            return ""

        pagamentos = resp["data"].get("data", [])
        if not pagamentos:
            return ""

        return pagamentos[0].get("invoiceUrl", "")

    def _cancelar_assinatura(self, subscription_id):
        headers = {"access_token": memory.asaas["API_KEY"]}

        try:
            resp = HttpClient._request(
                'DELETE',
                memory.asaas["API_URL"] + "/subscriptions/" + subscription_id,
                headers=headers
            )
            return resp and resp["status_code"] in [200, 204]
        except Exception:
            return False
