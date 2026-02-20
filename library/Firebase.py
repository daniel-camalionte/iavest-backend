from pyfcm import FCMNotification
import config.env as memory

class Firebase:
    """ Firebase
    """
    def __init__(self):
        self.service = FCMNotification(api_key=memory.firebase["API_KEY"])
        
    def publish(self, registration_id, message_title, message_body, data_message):
        """ publish
        """
        result = self.service.notify_single_device(
                                    registration_id=registration_id, 
                                    message_title=message_title, 
                                    message_body=message_body,
                                    data_message=data_message
                                )
        return result