from model.Assinatura import AssinaturaModel
from model.Plano import PlanoModel
from library.HttpClient import HttpClient
import config.env as memory
import json
from datetime import datetime

class AssinaturaRule():

    def __init__(self):
        pass

    def criar(self, id_usuario, data):
        plano_id = data.get("plano_id")

        # Buscar plano
        modPlano = PlanoModel()
        plano_data = modPlano.find_one(plano_id)

        if not plano_data:
            return {"success": False, "message": "Plano inválido"}, 400

        plano = plano_data[0]

        if not plano.get("ativo"):
            return {"success": False, "message": "Plano inválido"}, 400

        # Verificar assinatura ativa
        modAssinatura = AssinaturaModel()
        assinatura_ativa = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).find()

        if assinatura_ativa:
            return {"success": False, "message": "Usuário já possui assinatura ativa"}, 409

        # Criar assinatura no Mercado Pago
        mp_response, mp_error = self._criar_preapproval(plano)

        if not mp_response:
            return {"success": False, "message": "Erro ao criar assinatura no Mercado Pago", "detail": mp_error}, 500

        # Salvar no banco
        obj = {
            "id_usuario": id_usuario,
            "id_plano": plano_id,
            "mercadopago_subscription_id": mp_response.get("id", ""),
            "checkout_url": mp_response.get("init_point", ""),
            "status": "pending"
        }

        modAssinatura = AssinaturaModel()
        id_assinatura = modAssinatura.save(obj)

        if not id_assinatura:
            return {"success": False, "message": "Erro ao salvar assinatura"}, 500

        return {
            "success": True,
            "checkout_url": mp_response.get("init_point", ""),
            "assinatura_id": id_assinatura
        }, 200

    def status(self, id_usuario):
        modAssinatura = AssinaturaModel()
        assinatura = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).find()

        if not assinatura:
            return {"success": True, "tem_assinatura": False}, 200

        ass = assinatura[0]

        # Buscar plano
        modPlano = PlanoModel()
        plano_data = modPlano.find_one(ass["id_plano"])
        plano = plano_data[0] if plano_data else {}

        recursos = []
        if plano.get("recursos"):
            try:
                recursos = json.loads(plano["recursos"])
            except:
                recursos = []

        return {
            "success": True,
            "tem_assinatura": True,
            "assinatura": {
                "id": ass["id_assinatura"],
                "plano_nome": plano.get("nome", ""),
                "status": ass["status"],
                "data_inicio": str(ass["data_inicio"]) if ass.get("data_inicio") else None,
                "data_proxima_cobranca": str(ass["data_proxima_cobranca"]) if ass.get("data_proxima_cobranca") else None,
                "recursos": recursos
            }
        }, 200

    def cancelar(self, id_usuario):
        # Buscar assinatura ativa
        modAssinatura = AssinaturaModel()
        assinatura = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).find()

        if not assinatura:
            return {"success": False, "message": "Nenhuma assinatura ativa encontrada"}, 404

        ass = assinatura[0]

        # Cancelar no Mercado Pago
        mp_id = ass.get("mercadopago_subscription_id")
        if mp_id:
            self._cancelar_preapproval(mp_id)

        # Atualizar no banco
        obj = {
            "status": "cancelled",
            "data_fim": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        modAssinatura = AssinaturaModel()
        modAssinatura.update(obj, ass["id_assinatura"])

        return {"success": True, "message": "Assinatura cancelada com sucesso"}, 200

    def _cancelar_preapproval(self, preapproval_id):
        url = "https://api.mercadopago.com/preapproval/" + str(preapproval_id)

        headers = {
            "Authorization": "Bearer " + memory.mercadopago["ACCESS_TOKEN"],
            "Content-Type": "application/json"
        }

        try:
            response = HttpClient.put(url, headers=headers, payload={"status": "cancelled"})
            return response and response["status_code"] == 200
        except Exception:
            return False

    def _criar_preapproval(self, plano):
        url = "https://api.mercadopago.com/preapproval"

        headers = {
            "Authorization": "Bearer " + memory.mercadopago["ACCESS_TOKEN"],
            "Content-Type": "application/json"
        }

        payload = {
            "reason": plano["nome"] + " - IAvest",
            "back_url": memory.mercadopago["BACK_URL"],
            "status": "pending"
        }

        if memory.mercadopago.get("NOTIFICATION_URL"):
            payload["notification_url"] = memory.mercadopago["NOTIFICATION_URL"]

        # Plano com ID do ML: configurações recorrentes já estão no plano
        if plano.get("mercadopago_plan_id"):
            payload["preapproval_plan_id"] = plano["mercadopago_plan_id"]
        else:
            payload["auto_recurring"] = {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": float(plano["valor_original"]),
                "currency_id": "BRL"
            }

        try:
            response = HttpClient.post(url, headers=headers, payload=payload)

            if response and response["status_code"] in [200, 201]:
                return response["data"], None
            else:
                error = response["data"] if response else "Sem resposta"
                return None, str(error)

        except Exception as e:
            return None, str(e)
