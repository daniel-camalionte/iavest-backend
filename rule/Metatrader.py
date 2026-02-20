from flask_jwt_extended import create_access_token
from model.MetatraderConfigs import MetatraderConfigsModel
from model.MetatraderConfigsLog import MetatraderConfigsLogModel
from model.Generico import GenericoModel

import json
import time

class MetatraderLoginRule():

    def __init__(self):
        pass

    def login(self, data, ip=None):
        id_estrategia = data.get("id_estrategia")
        account_number = data.get("account_number")
        password = data.get("password")

        modMetatraderConfigs = MetatraderConfigsModel()

        dataMetatraderConfigs = modMetatraderConfigs.where(['account_number', '=', account_number]).where(['password', '=', password]).find()
        if not dataMetatraderConfigs:
            return {'usuario': 0, 'contrato': 0}, 404

        id_metatrader_configs = dataMetatraderConfigs[0].get("id_metatrader_configs")

        #registrar log
        modMetatraderConfigsLog = MetatraderConfigsLogModel()
        modMetatraderConfigsLog.save({
            "id_metatrader_configs": id_metatrader_configs,
            "connection_status": 'connected',
            "ip": ip
        })

        modGenerico = GenericoModel()
        sql = """SELECT
                    u.id_usuario AS usuario_id,
                    p.contrato AS plano_contrato
                 FROM metatrader_configs mc
                 INNER JOIN usuario u ON u.id_usuario = mc.id_usuario
                 INNER JOIN plano_usuario pu ON pu.id_usuario = u.id_usuario
                 INNER JOIN plano p ON p.id_plano = pu.id_plano
                 INNER JOIN estrategia e ON e.id_estrategia = %s
                 WHERE mc.account_number = %s"""

        retMetatraderConfigs = modGenerico.fetch(sql, [id_estrategia, account_number])
        if not retMetatraderConfigs:
            return {'usuario': 1, 'contrato': 0}, 404

        id_usuario = retMetatraderConfigs[0].get("usuario_id") or 0
        plano_contrato = retMetatraderConfigs[0].get("plano_contrato") or 0

        return {'usuario': 1, 'id_usuario': id_usuario,'contrato': plano_contrato}, 200
