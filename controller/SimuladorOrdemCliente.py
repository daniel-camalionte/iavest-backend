from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity

from rule.SimuladorOrdemCliente import SimuladorOrdemClienteRule
from rule.SimuladorAnaliseIa import SimuladorAnaliseIaRule
from model.ControllerError import ControllerError


class SimuladorOrdemListaController(MethodView):
    """GET  /simulador/ordem            — lista as ordens do cliente (com calculos)
       POST /simulador/ordem            — cria nova ordem"""

    @jwt_required
    def get(self):
        try:
            id_cliente = get_jwt_identity().get("id_usuario")
            status = request.args.get("status")
            data   = request.args.get("data")
            return SimuladorOrdemClienteRule.listar(id_cliente, status=status, data=data)
        except Exception as e:
            return ControllerError().default(e), 500

    @jwt_required
    def post(self):
        try:
            id_cliente = get_jwt_identity().get("id_usuario")
            body = request.get_json() or {}
            return SimuladorOrdemClienteRule.criar(id_cliente, body)
        except Exception as e:
            return ControllerError().default(e), 500


class SimuladorOrdemItemController(MethodView):
    """GET    /simulador/ordem/<id>     — detalhe (com calculos)
       DELETE /simulador/ordem/<id>     — exclui (cadastro equivocado)"""

    @jwt_required
    def get(self, id_ordem):
        try:
            id_cliente = get_jwt_identity().get("id_usuario")
            return SimuladorOrdemClienteRule.detalhe(id_cliente, id_ordem)
        except Exception as e:
            return ControllerError().default(e), 500

    @jwt_required
    def delete(self, id_ordem):
        try:
            id_cliente = get_jwt_identity().get("id_usuario")
            return SimuladorOrdemClienteRule.deletar(id_cliente, id_ordem)
        except Exception as e:
            return ControllerError().default(e), 500


class SimuladorOrdemEncerrarController(MethodView):
    """PUT /simulador/ordem/<id>/encerrar — encerra a ordem
       (encerrada_em obrigatório = horário do MT5; preco_saida opcional)"""

    @jwt_required
    def put(self, id_ordem):
        try:
            id_cliente = get_jwt_identity().get("id_usuario")
            body = request.get_json() or {}
            return SimuladorOrdemClienteRule.encerrar(id_cliente, id_ordem, body)
        except Exception as e:
            return ControllerError().default(e), 500


class SimuladorAnaliseIaController(MethodView):
    """GET /simulador/ordem/<id>/analise-ia — análise IA da posição (liberada por plano).
       Aberta = análise completa (cache por candle). Encerrada = texto genérico."""

    @jwt_required
    def get(self, id_ordem):
        try:
            id_cliente = get_jwt_identity().get("id_usuario")
            # TODO: gating por plano (definir qual plano libera) antes de seguir
            return SimuladorAnaliseIaRule.analisar(id_cliente, id_ordem)
        except Exception as e:
            return ControllerError().default(e), 500
