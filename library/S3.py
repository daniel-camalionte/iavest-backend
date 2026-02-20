import boto3
import config.env as memory

class S3:
    """ S3
    """
    def __init__(self):
        self.client = boto3.client(
                "s3",
                aws_access_key_id=memory.aws["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=memory.aws["AWS_SECRET_ACCESS_KEY"],
                region_name='sa-east-1'
            )
        
    def publish(self, path_local, bucket, path_bucket, mimetype):
        """ publish
        """
        response = self.client.upload_file(
                            Filename=path_local,
                            Bucket=bucket,
                            Key=path_bucket,
                            ExtraArgs={
                                "ContentType": mimetype,
                                "ACL": 'public-read'
                            }
                        )
        
        if self.client.meta.endpoint_url:
            url = "https://{0}.s3.sa-east-1.amazonaws.com/{1}".format(bucket, path_bucket)
            return url
        return 0