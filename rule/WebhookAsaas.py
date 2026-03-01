from model.Assinatura import AssinaturaModel
from model.Pagamento import PagamentoModel
from model.WebhookAsaas import WebhookAsaasModel
import json
from datetime import datetime, timedelta

class WebhookAsaasRule():

    def __init__(self):
        pass

    def processar(self, data):
        event = data.get("event", "")

        modWebhook = WebhookAsaasModel()
        id_webhook = modWebhook.save({
            "event": event,
            "payload": json.dumps(data),
            "status": "processing"
        })

        try:
            payment = data.get("payment", {})
            subscription_id = payment.get("subscription")

            if not subscription_id:
                modWebhook.update({"status": "finished"}, id_webhook)
                return {"success": True}, 200

            # Buscar assinatura no banco
            modAssinatura = AssinaturaModel()
            assinatura = modAssinatura.where(['asaas_subscription_id', '=', subscription_id]).find()

            if not assinatura:
                modWebhook.update({"status": "finished"}, id_webhook)
                return {"success": True}, 200

            ass = assinatura[0]

            if event in ["PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"]:
                now = datetime.now()
                proxima = now + timedelta(days=30)
                modAssinatura.update({
                    "status": "active",
                    "data_proxima_cobranca": proxima.strftime('%Y-%m-%d %H:%M:%S')
                }, ass["id_assinatura"])

                self._registrar_pagamento(ass["id_assinatura"], payment)

            elif event in ["PAYMENT_DELETED", "SUBSCRIPTION_DELETED", "SUBSCRIPTION_INACTIVATED", "PAYMENT_REFUNDED"]:
                modAssinatura.update({
                    "status": "cancelled",
                    "data_fim": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }, ass["id_assinatura"])

            elif event == "PAYMENT_OVERDUE":
                modAssinatura.update({"status": "overdue"}, ass["id_assinatura"])

            elif event == "PAYMENT_RESTORED":
                modAssinatura.update({"status": "pending"}, ass["id_assinatura"])

            modWebhook.update({
                "status": "finished",
                "response": json.dumps({"processed": event})
            }, id_webhook)

            return {"success": True}, 200

        except Exception as e:
            modWebhook.update({"status": "error", "erro": str(e)}, id_webhook)
            raise

    def _registrar_pagamento(self, id_assinatura, payment):
        modPagamento = PagamentoModel()

        payment_id = str(payment.get("id", ""))

        existente = modPagamento.where(['gateway_payment_id', '=', payment_id]).find()
        if existente:
            return

        modPagamento.save({
            "id_assinatura": id_assinatura,
            "gateway_payment_id": payment_id,
            "gateway": "asaas",
            "valor": str(payment.get("value", 0)),
            "status": payment.get("status", ""),
            "metodo_pagamento": payment.get("billingType", ""),
            "data_pagamento": payment.get("confirmedDate") or payment.get("dueDate", "")
        })
