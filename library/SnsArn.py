import boto3
import config.env as memory

class SnsArn:
    """ SnsArn
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

        self.client.subscribe(
                TopicArn=memory.aws["TOPIC_ARN"],
                Protocol='sms',
                Endpoint=phone  # <-- number who'll receive an SMS message.
            )
        
        publish = self.client.publish(
                    TopicArn=memory.aws["TOPIC_ARN"],
                    Message=message
                )

        return publish