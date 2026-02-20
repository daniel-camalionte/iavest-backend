from flask import g, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import time
import secrets
import jsonschema
import simplejson as json
import config.env as memory
import string

class Funcao:
    """ Funcao
    """
    @staticmethod                
    def formata_semana(dia):
        """ formata
        """
        switcher = {
            1: 'Segunda-feira',
            2: 'Terça-feira',
            3: 'Quarta-feira',
            4: 'Quinta-feira',
            5: 'Sexta-feira',
            6: 'Sábado',
            7: 'Domingo'
        }
        
        return switcher.get(dia, 'Invalid')

    @staticmethod 
    def data_ativa(dia, hora_inicio, hora_final):
        now = datetime.now()
        data = datetime(year=now.year, month=now.month, day=now.day)
        indice_da_semana = data.isoweekday()

        #para localtime necessário subtrair 3 hrs
        hour = now.hour - 3
        minute = now.minute
        
        #formatacao para poder comparar hora
        if minute < 10:
            minute = "{}{}".format(0, minute)

        hora_now = "{}{}".format(hour, minute)
        hora_now = int(hora_now)
        hora_inicio = int(hora_inicio.replace(':', ''))
        hora_final = int(hora_final.replace(':', ''))
        
        if indice_da_semana == dia and hora_now >= hora_inicio and hora_now <= hora_final:
            return True

        return False
        
    @staticmethod                
    def formata_data(tipo, unixtime):
        """ Data
        """
        #para localtime necessário subtrair 3 hrs
        #unixtime = unixtime - (3600*3)
        
        if tipo == 1:
            data = datetime.utcfromtimestamp(unixtime).strftime("%d/%m/%Y")
        
        if tipo == 2:
            data = datetime.utcfromtimestamp(unixtime).strftime("%d/%m/%Y %H:%M:%S")

        #formata data
        if tipo == 3:
            data = int(datetime.strptime(unixtime, '%d/%m/%Y').strftime("%s"))
        
        #formata data com hora
        if tipo == 4:
            data = int(datetime.strptime(unixtime, '%d/%m/%Y %H:%M:%S').strftime("%s"))
        
        return data

    @staticmethod                
    def rand(tipo, tamanho):
        """ Rand
        """

        #rand somente número 1 a 9
        if tipo == 1:
            code = ''.join([str(secrets.randbelow(9) + 1) for _ in range(tamanho)])
            return int(code)

        if tipo == 2:
            alphabet = string.ascii_uppercase.replace("O", "L") + string.digits.replace("0", "1")
            return ''.join(secrets.choice(alphabet) for _ in range(tamanho))

    @staticmethod                
    def schema(path_schema):
        """ schema
        """
        get_json = request.get_json()
        path_json = '{path}{schema}'.format(path = memory.utilits["PATH_SCHEMA"], schema = path_schema)
        with open(path_json, 'r') as f:
            schema_data = f.read()
        schema = json.loads(schema_data)
        try:
            jsonschema.validate(get_json, schema)
            return get_json
        except jsonschema.ValidationError as e:
            raise ValueError(e.schema["error_msg"])