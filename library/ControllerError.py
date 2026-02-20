# coding=utf-8
""" DOC
"""
from library.MySql import MySql
from werkzeug.exceptions import BadRequest
import sys
import os

class ControllerError:
    """ ControllerError
    """

    def MySQL(self, exception):
        
        self.__logar(exception)

        return {"sucesso": False, "msg": str(exception)}


    def badRequests(self, exception):
        """ badRequest
        """

        self.__logar(exception)

        return {"sucesso": False, "msg": str(exception)}

    def default(self, exception):
        """ badRequest
        """

        self.__logar(exception)

        return {"sucesso": False, "msg": str(exception)}

    def __logar(self, exception):
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fpath = exc_tb.tb_frame.f_code.co_filename

        print(str(exception), type(exception),
              exc_type, fpath, exc_tb.tb_lineno)

        return True