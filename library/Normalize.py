from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

import time

class Normalize:
    """ Funcao
    """
    
    @staticmethod                
    def unixtime_to_data(tipo, unixtime):
        """ formata
        """
        #para localtime necessário subtrair 3 hrs
        unixtime = unixtime - (3600*3)
        
        if tipo == 1:
            data = datetime.utcfromtimestamp(unixtime).strftime("%d/%m/%Y")
        
        if tipo == 2:
            data = datetime.utcfromtimestamp(unixtime).strftime("%d/%m/%Y %H:%M:%S")
        
        return data
    
    @jwt_required()
    def jwt_identity():
        identity = get_jwt_identity()
        return identity