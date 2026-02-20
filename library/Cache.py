from library.MongoDB import MongoDB

class Cache:
    
    def __init__(self):
        self.mongo = MongoDB()
        self.mongo_curr = self.mongo.open()

    def find(self, collection):
        """ busca collection
        """
        collection = self.mongo_curr[collection]
        data = collection.find()
        collection.close

        if data.count() > 0:  
            return data
        return 0

    def find_one(self, collection, codigo):
        """ busca collection
        """
        collection = self.mongo_curr[collection]
        data = collection.find_one({ "codigo": codigo })
        collection.close

        return data

    def find_obj(self, collection, obj):
        """ busca collection
        """
        collection = self.mongo_curr[collection]
        data = collection.find_one(obj)
        collection.close

        return data

    def record(self, collection, data=None):
        """ grava collection
        """
        collection = self.mongo_curr[collection]
        collection.insert_one(data)
        collection.close
    
    def remove(self, collection, data=None):
        """ grava collection
        """
        collection = self.mongo_curr[collection]
        collection.remove(data)
        collection.close