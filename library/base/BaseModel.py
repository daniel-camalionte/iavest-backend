from library.base.QueryBuilder import QueryBuilder
from library.MySql import MySql
from model.ControllerError import ControllerError

import json

class BaseModel(QueryBuilder):

    def __init__(self):
        self._field = ""
        self._where = []
        self._order = ""
        self._limit = ""
        self._offset = ""
        self._debug = 0
        self._params = []

    def find(self, debug=None):
        self._debug = debug
        self._sql, self._params = self.buildSelect(self._field, 0, self._where, self._order, self._limit, self._offset)
        return self.execute()

    def find_one(self, id=None, debug=None):
        self._debug = debug
        self._sql, self._params = self.buildSelect(self._field, id)
        return self.execute()

    def save(self, obj, debug=None):
        self._debug = debug
        self._sql, self._params = self.buildSave(obj)
        return self.execute()

    def update(self, obj, id, debug=None):
        self._debug = debug
        self._sql, self._params = self.buildUpdate(obj, id)
        return self.execute()

    def delete(self, id, debug=None):
        self._debug = debug
        self._sql, self._params = self.buildDelete(id)
        return self.execute()

    def field(self, data):
        self._field = data
        return self

    def where(self, data):
        self._where.append(data)
        return self

    def order(self, field, tipo):
        self._order = ""
        self._order = self.buildOrder(field, tipo)
        return self

    def limit(self, limit):
        self._limit = ""
        self._limit = self.buildLimit(limit)
        return self

    def offset(self, offset):
        self._offset = ""
        self._offset = self.buildOffset(offset)
        return self

    def execute(self, sql=None, params=None, debug=None):
        try:
            if sql:
                self._sql = sql
                self._params = params if params is not None else []

            if self._debug or debug:
                self._debug = 0
                return self._sql

            self.mysql = MySql()
            self.curr = self.mysql.open()
            rows_count = self.curr.execute(self._sql, self._params if self._params else None)

            #clear
            self._field = ""
            self._where = []
            self._order = ""
            self._limit = ""
            self._params = []

            if("SELECT" in self._sql):
                self._retorno = self.curr.fetchall() if rows_count > 0 else []
                self.curr.close()
                self.mysql.close()
                return self._retorno

            if("INSERT" in self._sql):
                self.mysql.commit()
                codigo = self.curr.lastrowid
                self._retorno = codigo if codigo > 0 else 0
                self.curr.close()
                self.mysql.close()
                return self._retorno

            if("UPDATE" in self._sql):
                self.mysql.commit()
                self._retorno = 1 if self.curr.rowcount > 0 else 0
                self.curr.close()
                self.mysql.close()
                return self._retorno

            if("DELETE" in self._sql):
                self.mysql.commit()
                self._retorno = 1 if self.curr.rowcount > 0 else 0
                self.curr.close()
                self.mysql.close()
                return self._retorno

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
