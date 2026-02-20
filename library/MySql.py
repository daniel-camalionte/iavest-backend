import config.env as memory

import pymysql

try:
    from dbutils.pooled_db import PooledDB
    _has_pooling = True
except ImportError:
    _has_pooling = False

_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            host=memory.mysql["DB_HOSTNAME"],
            port=memory.mysql["DB_PORT"],
            user=memory.mysql["DB_USER"],
            passwd=memory.mysql["DB_PASSWORD"],
            db=memory.mysql["DB_NAME"],
            cursorclass=pymysql.cursors.DictCursor
        )
    return _pool

def _direct_connect():
    return pymysql.connect(
        host=memory.mysql["DB_HOSTNAME"],
        port=memory.mysql["DB_PORT"],
        user=memory.mysql["DB_USER"],
        passwd=memory.mysql["DB_PASSWORD"],
        db=memory.mysql["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor
    )


class MySql:
    """ Mysql
    """
    def __init__(self):
        if _has_pooling:
            self.conn = _get_pool().connection()
        else:
            self.conn = _direct_connect()

    def open(self):
        """ open
        """
        return self.conn.cursor()

    def close(self):
        """ close
        """
        return self.conn.close()

    def commit(self):
        """ commit
        """
        return self.conn.commit()

    def rollback(self):
        """ rollback
        """
        return self.conn.rollback()

    def fetch(self, sql, parameter=0):
        curr = self.open()
        if parameter:
            curr.execute(sql, parameter)
        else:
            curr.execute(sql)
        result = curr.fetchall()
        self.close()
        return result

    def execute(self, sql, parameter):
        curr = self.open()
        curr.execute(sql, parameter)
        self.close()
