import boto3
import config.env as memory

class Sns:
    """ Sns
    """
    def __init__(self):
        self.client = boto3.client(
                'sns',
                aws_access_key_id=memory.aws["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=memory.aws["AWS_SECRET_ACCESS_KEY"],
                region_name='us-east-1'
            )
        
    def send(self, phone, message):
        """ send
        """

        publish = self.client.publish(
                    PhoneNumber=phone,
                    Message=message
                )

        return publish