from pymongo import MongoClient

import config.env as memory

class MongoDB:
    """ MongoDB
    """
    def __init__(self):
        self.client = MongoClient(memory.mongodb["DB_HOSTNAME"],
                          username=memory.mongodb["DB_USER"],
                          password=memory.mongodb["DB_PASSWORD"],
                          authSource=memory.mongodb["DB_NAME"],
                          authMechanism='SCRAM-SHA-256')
        
    def open(self):
        """ open
        """

        mydb = self.client[memory.mongodb["DB_NAME"]]
        return mydb