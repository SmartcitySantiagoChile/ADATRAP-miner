import boto3
from decouple import config


class AWSSession:
    """
    Class to interact wit Amazon Web Service (AWS) API through boto3 library
    """

    def __init__(self):
        self.session = boto3.Session(
            aws_access_key_id=config("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"),
            region_name=config("REGION_NAME"),
        )

    def create_key_pair(self):
        ec2 = self.session.resource("ec2")
        outfile = open("ec2-keypair.pem", "w")
        key_pair = ec2.create_key_pair(KeyName="ec2-keypair")
        key_pair_out = str(key_pair.key_material)
        print(key_pair_out)
        outfile.write(key_pair_out)

    def create_ec2_instance(self):
        ec2 = self.session.resource("ec2")
        instances = ec2.create_instances(
            ImageId="ami-02f50d6aef81e691a",
            MinCount=1,
            MaxCount=2,
            InstanceType="t2.micro",
            KeyName="ec2-keypair",
        )
        return instances
