from library.MongoDB import MongoDB
from flask import g, request
import re

class Permissao:
    """ Funcao
    """   
    def __init__(self):
        self.mongo = MongoDB()
        self.mongo_curr = self.mongo.open()

    #@staticmethod                
    def rota(self, id):
        """ rota
        """
        
        collection = self.mongo_curr["permissao"]
        permissao = collection.find_one({ "id_usuario": id})
        collection.close

        path = request.path
        method = request.environ.get("REQUEST_METHOD")
        
        arr_rota = [r for r in permissao.get("permissao") if r.get("rota") == path and r.get(method) == 1]
        verifica = True if len(arr_rota) > 0 else False

        return verifica