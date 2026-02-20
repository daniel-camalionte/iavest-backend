from library.base.BaseModel import BaseModel
from library.MySql import MySql

class GenericoModel(BaseModel):

    def __init__(self):
        super().__init__()
        pass

    def table(self):
        pass

    def pk(self):
        pass

    def fields(self):
        pass

    def fetch(self, sql, params=None):
        mysql = MySql()
        result = mysql.fetch(sql, params)
        return result
