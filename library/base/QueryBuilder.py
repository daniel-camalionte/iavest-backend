import abc

class QueryBuilder(abc.ABC):

    def __init__(self):
        pass

    def buildSelect(self, obj=None, id=None, where=None, order=None, limit=None, offset=None):
        fields = self.fields()
        field_all = ''
        condicao = ''
        params = []

        order = order if order else ''
        limit = limit if limit else ''
        offset = offset if offset else ''

        if id:
            condicao, params = self.buildWhere([[self.pk(), '=', id]])

        if obj:
            fields = obj

        for key in fields:
            field_all = field_all + str(key) +" as " + str(fields[key]) + ","

        field_all = field_all[:-1]

        if where:
            condicao, params = self.buildWhere(where)

        sql = "SELECT {field_all} FROM {table} {condicao} {order} {limit} {offset}".format(
            field_all=field_all, table=self.table(), condicao=condicao,
            order=order, limit=limit, offset=offset)

        return sql, params

    def buildSave(self, obj):
        arr_field = []
        params = []
        placeholders = []

        for key in obj:
            arr_field.append(key)
            placeholders.append('%s')
            params.append(obj[key])

        field = ','.join(map(str, arr_field))
        sql = "INSERT INTO {table} ({field}) VALUES ({placeholders})".format(
            table=self.table(), field=field, placeholders=','.join(placeholders))
        return sql, params

    def buildUpdate(self, obj, id):
        set_parts = []
        params = []

        for key in obj:
            set_parts.append(key + " = %s")
            params.append(obj[key])

        params.append(id)

        sql = "UPDATE {table} SET {value} WHERE {pk} = %s".format(
            table=self.table(), value=','.join(set_parts), pk=self.pk())
        return sql, params

    def buildDelete(self, id):
        sql = "DELETE FROM {table} WHERE {pk} = %s".format(table=self.table(), pk=self.pk())
        return sql, [id]

    @staticmethod
    def buildWhere(data=None):
        where = 'WHERE 1=1'
        params = []
        for key in data:
            if key[2] is None:
                where += " AND " + key[0] + " IS NULL"
            else:
                where += " AND " + key[0] + " " + key[1] + " %s"
                params.append(key[2])

        return where, params

    @staticmethod
    def buildOrder(field, tipo):
        order = 'ORDER BY {field} {tipo}'.format(field=field, tipo=tipo)
        return order

    @staticmethod
    def buildLimit(limit):
        limit = 'LIMIT {}'.format(int(limit))
        return limit

    @staticmethod
    def buildOffset(offset):
        offset = 'OFFSET {}'.format(int(offset))
        return offset

    @abc.abstractmethod
    def table(self):
        pass

    @abc.abstractmethod
    def fields(self):
        pass

    @abc.abstractmethod
    def pk(self):
        pass
