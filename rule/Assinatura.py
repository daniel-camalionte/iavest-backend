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

        if not plano.get("preapproval_plan_id"):
            return {"success": False, "message": "Plano sem configuração no Mercado Pago"}, 400

        # Verificar assinatura ativa
        modAssinatura = AssinaturaModel()
        assinatura_ativa = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).find()

        if assinatura_ativa:
            return {"success": False, "message": "Usuário já possui assinatura ativa"}, 409

        # Obter URL do plano: usa a salva no banco ou busca na API do ML
        plan_url = plano.get("mercadopago_plan_url") or self._buscar_url_plano(plano["preapproval_plan_id"])

        if not plan_url:
            return {"success": False, "message": "Não foi possível obter URL de checkout do plano"}, 500

        # Adiciona external_reference para identificar o usuário no webhook
        separator = "&" if "?" in plan_url else "?"
        checkout_url = "{}{}external_reference={}".format(plan_url, separator, id_usuario)

        # Reutilizar checkout pendente se o usuário ainda não concluiu
        assinatura_pendente = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['id_plano', '=', plano_id]).where(['status', '=', 'pending']).find()

        if assinatura_pendente:
            return {
                "success": True,
                "checkout_url": checkout_url,
                "assinatura_id": assinatura_pendente[0]["id_assinatura"]
            }, 200

        # Salvar registro pendente — webhook ativará ao receber confirmação do ML
        obj = {
            "id_usuario": id_usuario,
            "id_plano": plano_id,
            "checkout_url": checkout_url,
            "status": "pending"
        }

        id_assinatura = modAssinatura.save(obj)

        if not id_assinatura:
            return {"success": False, "message": "Erro ao registrar assinatura"}, 500

        return {
            "success": True,
            "checkout_url": checkout_url,
            "assinatura_id": id_assinatura
        }, 200

    def status(self, id_usuario):
        modAssinatura = AssinaturaModel()
        assinatura = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).find()

        if not assinatura:
            return {"success": True, "tem_assinatura": False}, 200

        ass = assinatura[0]

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
        modAssinatura = AssinaturaModel()
        assinatura = modAssinatura.where(['id_usuario', '=', id_usuario]).where(['status', '=', 'active']).find()

        if not assinatura:
            return {"success": False, "message": "Nenhuma assinatura ativa encontrada"}, 404

        ass = assinatura[0]

        mp_id = ass.get("mercadopago_subscription_id")
        if mp_id:
            self._cancelar_preapproval(mp_id)

        modAssinatura.update({
            "status": "cancelled",
            "data_fim": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, ass["id_assinatura"])

        return {"success": True, "message": "Assinatura cancelada com sucesso"}, 200

    def _buscar_url_plano(self, preapproval_plan_id):
        url = "https://api.mercadopago.com/preapproval_plan/" + preapproval_plan_id

        headers = {
            "Authorization": "Bearer " + memory.mercadopago["ACCESS_TOKEN"]
        }

        try:
            response = HttpClient.get(url, headers=headers)
            if response and response["status_code"] == 200:
                return response["data"].get("init_point", "")
            return None
        except Exception:
            return None

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
