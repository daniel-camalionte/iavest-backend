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
import sentry_sdk

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

          # Log Sentry
          status_code = dados_login[1] if isinstance(dados_login, tuple) else 200
          resp = dados_login[0] if isinstance(dados_login, tuple) else dados_login
          level = "info" if status_code == 200 else "warning"

          sentry_sdk.set_context("request", {"payload": data, "ip": ip})
          sentry_sdk.set_context("response", {"body": resp, "status_code": status_code})
          sentry_sdk.capture_message("MT Login: " + ("sucesso" if status_code == 200 else "falha"), level=level)

          return dados_login

        except json.JSONDecodeError as e:
            sentry_sdk.set_context("request", {"raw": request.data.decode('utf-8') if request.data else None})
            sentry_sdk.capture_exception(e)
            return {"msg": "JSON inválido: " + str(e)}, 422
        except Exception as e:
            sentry_sdk.set_context("request", {"payload": data})
            sentry_sdk.capture_exception(e)
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

          # Log Sentry
          status_code = result[1] if isinstance(result, tuple) else 200
          resp = result[0] if isinstance(result, tuple) else result
          level = "info" if status_code == 200 else "error"

          sentry_sdk.set_context("request", {"payload": data})
          sentry_sdk.set_context("response", {"body": resp, "status_code": status_code})
          sentry_sdk.capture_message("Trade Start: " + ("sucesso" if status_code == 200 else "erro"), level=level)

          return result

        except json.JSONDecodeError as e:
            sentry_sdk.set_context("request", {"raw": request.data.decode('utf-8') if request.data else None})
            sentry_sdk.capture_exception(e)
            return {"msg": "JSON inválido: " + str(e)}, 422
        except Exception as e:
            sentry_sdk.set_context("request", {"payload": data})
            sentry_sdk.capture_exception(e)
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

          # Log Sentry
          status_code = result[1] if isinstance(result, tuple) else 200
          resp = result[0] if isinstance(result, tuple) else result
          level = "info" if status_code == 200 else "error"

          sentry_sdk.set_context("request", {"payload": data})
          sentry_sdk.set_context("response", {"body": resp, "status_code": status_code})
          sentry_sdk.capture_message("Trade Exit: " + ("sucesso" if status_code == 200 else "erro"), level=level)

          return result

        except json.JSONDecodeError as e:
            sentry_sdk.set_context("request", {"raw": request.data.decode('utf-8') if request.data else None})
            sentry_sdk.capture_exception(e)
            return {"msg": "JSON inválido: " + str(e)}, 422
        except Exception as e:
            sentry_sdk.set_context("request", {"payload": data})
            sentry_sdk.capture_exception(e)
            msg = ControllerError().default(e)
            return msg, 500
