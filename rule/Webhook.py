from model.Assinatura import AssinaturaModel
from model.Pagamento import PagamentoModel
from model.WebhookMercadopago import WebhookMercadopagoModel
from library.HttpClient import HttpClient
import config.env as memory
import json
from datetime import datetime, timedelta

class WebhookRule():

    def __init__(self):
        pass

    def mercadopago(self, data):
        # Salvar registro na tabela com status='processing'
        modWebhook = WebhookMercadopagoModel()
        id_webhook = modWebhook.save({
            "action": data.get("action", ""),
            "payload": json.dumps(data),
            "status": "processing"
        })

        return self._processar(data, id_webhook)

    def reprocessar(self, id_webhook):
        modWebhook = WebhookMercadopagoModel()
        registro = modWebhook.find_one(id_webhook)

        if not registro:
            return {"success": False, "message": "Webhook não encontrado"}, 404

        # Extrair payload salvo
        try:
            data = json.loads(registro[0]["payload"])
        except Exception:
            return {"success": False, "message": "Payload inválido"}, 400

        # Atualizar status para processing e incrementar attempts
        modWebhook2 = WebhookMercadopagoModel()
        modWebhook2.update({
            "status": "processing",
            "attempts": int(registro[0].get("attempts", 1)) + 1
        }, id_webhook)

        return self._processar(data, id_webhook)

    def _processar(self, data, id_webhook):
        try:
            action = data.get("action", "")
            payment_id = None

            if data.get("data") and data["data"].get("id"):
                payment_id = str(data["data"]["id"])

            if not payment_id:
                self._finalizar_webhook(id_webhook, "finished")
                return {"success": True}, 200

            # Buscar detalhes do pagamento na API do MP
            payment = self._buscar_pagamento(payment_id)

            if not payment:
                self._finalizar_webhook(id_webhook, "finished")
                return {"success": True}, 200

            # Salvar response do MercadoPago
            self._finalizar_webhook(id_webhook, "finished", payment)

            # Identificar assinatura pelo preapproval_id
            preapproval_id = payment.get("metadata", {}).get("preapproval_id", "")

            if not preapproval_id:
                preapproval_id = self._buscar_preapproval_por_payment(payment)

            if not preapproval_id:
                return {"success": True}, 200

            # Buscar assinatura no banco
            modAssinatura = AssinaturaModel()
            assinatura = modAssinatura.where(['mercadopago_subscription_id', '=', preapproval_id]).find()

            if not assinatura:
                return {"success": True}, 200

            ass = assinatura[0]

            # Registrar pagamento
            self._registrar_pagamento(ass["id_assinatura"], payment)

            # Atualizar status da assinatura baseado na acao
            payment_status = payment.get("status", "")

            if payment_status == "approved":
                now = datetime.now()
                proxima = now + timedelta(days=30)

                obj = {
                    "status": "active",
                    "data_inicio": now.strftime('%Y-%m-%d %H:%M:%S'),
                    "data_proxima_cobranca": proxima.strftime('%Y-%m-%d %H:%M:%S')
                }

                modAssinatura = AssinaturaModel()
                modAssinatura.update(obj, ass["id_assinatura"])

            return {"success": True}, 200

        except Exception as e:
            self._finalizar_webhook(id_webhook, "error", erro=str(e))
            raise

    def _finalizar_webhook(self, id_webhook, status, response=None, erro=None):
        try:
            modWebhook = WebhookMercadopagoModel()
            obj = {"status": status}
            if response is not None:
                obj["response"] = json.dumps(response)
            if erro is not None:
                obj["erro"] = erro
            modWebhook.update(obj, id_webhook)
        except Exception:
            pass

    def _buscar_pagamento(self, payment_id):
        url = "https://api.mercadopago.com/v1/payments/" + payment_id

        headers = {
            "Authorization": "Bearer " + memory.mercadopago["ACCESS_TOKEN"]
        }

        try:
            response = HttpClient.get(url, headers=headers)
            if response and response["status_code"] == 200:
                return response["data"]
            return None
        except Exception:
            return None

    def _buscar_preapproval_por_payment(self, payment):
        # Tentar extrair preapproval_id de campos alternativos
        for field in ["preapproval_id", "external_reference"]:
            value = payment.get(field)
            if value:
                return value

        # Tentar extrair de point_of_interaction.transaction_data.subscription_id
        try:
            subscription_id = payment.get("point_of_interaction", {}).get("transaction_data", {}).get("subscription_id")
            if subscription_id:
                return subscription_id
        except Exception:
            pass

        return None

    def _registrar_pagamento(self, id_assinatura, payment):
        modPagamento = PagamentoModel()

        # Verificar se pagamento ja foi registrado
        existente = modPagamento.where(['mercadopago_payment_id', '=', str(payment.get("id", ""))]).find()

        if existente:
            return

        obj = {
            "id_assinatura": id_assinatura,
            "mercadopago_payment_id": str(payment.get("id", "")),
            "valor": str(payment.get("transaction_amount", 0)),
            "status": payment.get("status", ""),
            "status_detail": payment.get("status_detail", ""),
            "metodo_pagamento": payment.get("payment_method_id", ""),
            "data_pagamento": payment.get("date_approved", payment.get("date_created", ""))
        }

        modPagamento.save(obj)
