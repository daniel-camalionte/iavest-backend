from model.IpnMercadopago import IpnMercadopagoModel
from model.Assinatura import AssinaturaModel
from model.Pagamento import PagamentoModel
from library.HttpClient import HttpClient
import config.env as memory
import sentry_sdk
import json
from datetime import datetime, timedelta

class IpnMercadopagoRule():

    def __init__(self):
        pass

    def processar(self, topic, resource_id):
        # Salvar notificacao recebida
        modIpn = IpnMercadopagoModel()
        id_ipn = modIpn.save({
            "topic": topic,
            "resource_id": resource_id,
            "status": "pending"
        })

        sentry_sdk.add_breadcrumb(
            category="ipn",
            message="IPN MP recebida",
            data={"topic": topic, "resource_id": resource_id, "id_ipn": id_ipn},
            level="info"
        )

        try:
            if topic == "payment":
                self._processar_payment(id_ipn, resource_id)
            elif topic == "merchant_order":
                self._processar_merchant_order(id_ipn, resource_id)
            else:
                self._atualizar_ipn(id_ipn, "processed", None, None)

        except Exception as e:
            self._atualizar_ipn(id_ipn, "error", None, str(e))
            sentry_sdk.capture_exception(e)

        return {"success": True}, 200

    def _processar_payment(self, id_ipn, payment_id):
        url = "https://api.mercadopago.com/v1/payments/" + str(payment_id)
        headers = {
            "Authorization": "Bearer " + memory.mercadopago["ACCESS_TOKEN"]
        }

        response = HttpClient.get(url, headers=headers)

        if not response or response["status_code"] != 200:
            erro = response["data"] if response else "Sem resposta"
            self._atualizar_ipn(id_ipn, "error", json.dumps(erro, default=str), "Erro ao buscar pagamento na API")
            return

        payment = response["data"]
        self._atualizar_ipn(id_ipn, "processed", json.dumps(payment, default=str), None)

        # Buscar preapproval_id no pagamento
        preapproval_id = payment.get("metadata", {}).get("preapproval_id", "")
        if not preapproval_id:
            for field in ["preapproval_id", "external_reference"]:
                value = payment.get(field)
                if value:
                    preapproval_id = value
                    break

        if not preapproval_id:
            sentry_sdk.capture_message("IPN MP: preapproval_id nao encontrado no payment " + str(payment_id), level="warning")
            return

        # Buscar assinatura no banco
        modAssinatura = AssinaturaModel()
        assinatura = modAssinatura.where(['mercadopago_subscription_id', '=', preapproval_id]).find()

        if not assinatura:
            sentry_sdk.capture_message("IPN MP: assinatura nao encontrada para preapproval " + str(preapproval_id), level="warning")
            return

        ass = assinatura[0]

        # Registrar pagamento
        self._registrar_pagamento(ass["id_assinatura"], payment)

        # Atualizar assinatura se aprovado
        if payment.get("status") == "approved":
            now = datetime.now()
            proxima = now + timedelta(days=30)

            modAssinatura = AssinaturaModel()
            modAssinatura.update({
                "status": "active",
                "data_inicio": now.strftime('%Y-%m-%d %H:%M:%S'),
                "data_proxima_cobranca": proxima.strftime('%Y-%m-%d %H:%M:%S')
            }, ass["id_assinatura"])

        sentry_sdk.capture_message("IPN MP: payment processado com sucesso", level="info")

    def _processar_merchant_order(self, id_ipn, order_id):
        url = "https://api.mercadopago.com/merchant_orders/" + str(order_id)
        headers = {
            "Authorization": "Bearer " + memory.mercadopago["ACCESS_TOKEN"]
        }

        response = HttpClient.get(url, headers=headers)

        if not response or response["status_code"] != 200:
            erro = response["data"] if response else "Sem resposta"
            self._atualizar_ipn(id_ipn, "error", json.dumps(erro, default=str), "Erro ao buscar merchant_order na API")
            return

        order = response["data"]
        self._atualizar_ipn(id_ipn, "processed", json.dumps(order, default=str), None)

        sentry_sdk.capture_message("IPN MP: merchant_order processada", level="info")

    def _registrar_pagamento(self, id_assinatura, payment):
        modPagamento = PagamentoModel()

        existente = modPagamento.where(['mercadopago_payment_id', '=', str(payment.get("id", ""))]).find()
        if existente:
            return

        modPagamento.save({
            "id_assinatura": id_assinatura,
            "mercadopago_payment_id": str(payment.get("id", "")),
            "valor": str(payment.get("transaction_amount", 0)),
            "status": payment.get("status", ""),
            "status_detail": payment.get("status_detail", ""),
            "metodo_pagamento": payment.get("payment_method_id", ""),
            "data_pagamento": payment.get("date_approved", payment.get("date_created", ""))
        })

    def _atualizar_ipn(self, id_ipn, status, payload, erro):
        modIpn = IpnMercadopagoModel()
        obj = {"status": status}

        if payload:
            obj["payload"] = payload
        if erro:
            obj["erro"] = erro
        if status in ["processed", "error"]:
            obj["processed_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        modIpn.update(obj, id_ipn)
