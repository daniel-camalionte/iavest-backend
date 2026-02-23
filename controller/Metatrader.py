from flask import g, request
from flask.views import MethodView
from flask_restful import reqparse
from flask_jwt_extended import jwt_required, get_raw_jwt
from rule.Metatrader import MetatraderLoginRule
from rule.MetatraderTrade import MetatraderTradeRule
from library.Funcao import Funcao
from blacklist import BLACKLIST
from model.ControllerError import ControllerError

import re
import json

class MetatraderLoginController(MethodView):
    def post(self):
        try:
          ret = {}

          data = None

          # Tenta pegar do form data (formato: payload={json})
          if request.form and 'payload' in request.form:
              payload_str = request.form.get('payload')
              data = json.loads(payload_str)

          # Tenta pegar do body raw (formato: payload={json})
          if not data and request.data:
              raw_data = request.data.decode('utf-8')
              if raw_data.startswith('payload='):
                  payload_str = raw_data[8:]  # Remove "payload="
                  data = json.loads(payload_str)
              else:
                  # Tenta como JSON puro
                  data = json.loads(raw_data)

          # Tenta como JSON direto
          if not data:
              data = request.get_json(force=True, silent=True)
              if isinstance(data, str):
                  data = json.loads(data)

          ip = request.headers.get('X-Forwarded-For', request.remote_addr)
          if ip and ',' in ip:
              ip = ip.split(',')[0].strip()

          ruleMetatraderLogin = MetatraderLoginRule()
          dados_login = ruleMetatraderLogin.login(data, ip)

          return dados_login

        except json.JSONDecodeError as e:
            return {"msg": "JSON inválido: " + str(e)}, 422
        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500


class MetatraderTradeStartController(MethodView):
    def post(self):
        data = None
        try:
          # Tenta pegar do form data (formato: payload={json})
          if request.form and 'payload' in request.form:
              payload_str = request.form.get('payload')
              data = json.loads(payload_str)

          # Tenta pegar do body raw (formato: payload={json})
          if not data and request.data:
              raw_data = request.data.decode('utf-8')
              if raw_data.startswith('payload='):
                  payload_str = raw_data[8:]  # Remove "payload="
                  data = json.loads(payload_str)
              else:
                  # Tenta como JSON puro
                  data = json.loads(raw_data)

          # Tenta como JSON direto
          if not data:
              data = request.get_json(force=True, silent=True)
              if isinstance(data, str):
                  data = json.loads(data)

          ruleMetatraderTrade = MetatraderTradeRule()
          result = ruleMetatraderTrade.create(data)

          return result

        except json.JSONDecodeError as e:
            return {"msg": "JSON inválido: " + str(e)}, 422
        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500


class MetatraderTradeExitController(MethodView):
    def post(self):
        data = None
        try:
          # Tenta pegar do form data (formato: payload={json})
          if request.form and 'payload' in request.form:
              payload_str = request.form.get('payload')
              data = json.loads(payload_str)

          # Tenta pegar do body raw (formato: payload={json})
          if not data and request.data:
              raw_data = request.data.decode('utf-8')
              if raw_data.startswith('payload='):
                  payload_str = raw_data[8:]  # Remove "payload="
                  data = json.loads(payload_str)
              else:
                  # Tenta como JSON puro
                  data = json.loads(raw_data)

          # Tenta como JSON direto
          if not data:
              data = request.get_json(force=True, silent=True)
              if isinstance(data, str):
                  data = json.loads(data)

          ruleMetatraderTrade = MetatraderTradeRule()
          result = ruleMetatraderTrade.close(data)

          return result

        except json.JSONDecodeError as e:
            return {"msg": "JSON inválido: " + str(e)}, 422
        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
