import time

import boto3
from decouple import config


class AWSSession:
    """
    Class to interact with Amazon Web Service (AWS) API through boto3 library
    """

    def __init__(self):
        self.session = boto3.Session(
            aws_access_key_id=config("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"),
            region_name=config("REGION_NAME"),
        )
        self.log_group = config("LOG_GROUP")

    def create_key_pair(self):
        """
        Create a key_pair with the ec2-keypair name.
        The ec2-keypair.pem file will be saved at root folder.
        """
        ec2 = self.session.resource("ec2")
        outfile = open("ec2-keypair.pem", "w")
        key_pair = ec2.create_key_pair(KeyName="ec2-keypair")
        key_pair_out = str(key_pair.key_material)
        outfile.write(key_pair_out)

    def create_ec2_instance(self):
        """
        Create a EC2 instance
        :return: instance id
        """
        ec2 = self.session.resource("ec2")
        instances = ec2.create_instances(
            ImageId="ami-02f50d6aef81e691a",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            KeyName="ec2-keypair",
        )
        return instances

    def run_ec2_instance(self, date):
        """
        Create an EC2 instance and next run a given command
        :return: instance id
        """
        ec2 = self.session.client("ec2")
        env_file = self.read_env_file()
        with open('windows_script') as f:
            lines = f.read()
            lines = lines.replace('EC2DATE', date).replace("ENV_DATA",
                                                                                              env_file)
            script = lines
            instances = ec2.run_instances(
                ImageId=config("AMI_ID"),
                MinCount=1,
                MaxCount=1,
                InstanceType="t2.micro",
                KeyName="ec2-keypair",
                UserData=script,
                Monitoring={"Enabled": True},
            )
        return instances

    def execute_commands(self, commands, instance_id):
        res = self.session.client("ssm").send_command(
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
            InstanceIds=[instance_id],
        )
        return res

    def create_log_stream(self, name):
        """
        Create a Log Stream with given name
        :param name: name of the Log Stream
        """
        logs = self.session.client("logs")
        logs.create_log_stream(logGroupName=self.log_group, logStreamName=name)

    def send_log_event(self, log_stream_name, message):
        """
        Send a Log Event to a Log Stream
        :param log_stream_name: name of the Log Stream
        :param message: message to be logged
        :return: log event response
        """
        token = self.get_last_token_event(log_stream_name)
        logs = self.session.client("logs")
        timestamp = int(round(time.time() * 1000))

        args = {
            "logGroupName": self.log_group,
            "logStreamName": log_stream_name,
            "logEvents": [
                {
                    "timestamp": timestamp,
                    "message": f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{message}",
                }
            ],
        }
        if token:
            args["sequenceToken"] = token
        response = logs.put_log_events(**args)
        return response

    def get_last_token_event(self, log_stream_name):
        """
        Get last token event for a log stream. It is needed for an existing Log Stream.
        :param log_stream_name: Log Stream name
        """
        logs = self.session.client("logs")
        token = (
            logs.describe_log_streams(
                logGroupName=self.log_group,
                logStreamNamePrefix=log_stream_name,
            )
                .get("logStreams")[0]
                .get("uploadSequenceToken")
        )
        return token

    def create_log_group(self, group_name, retention=7):
        logs = self.session.client("logs")
        response = logs.create_log_group(
            logGroupName=group_name,
        )
        logs.put_resource_policy(policyName="string", policyDocument="string")
        return response

    def get_instance_id(self):
        import socket

        hostname = socket.gethostname()
        session = self.session.client("ec2")
        for reservation in session.describe_instances()["Reservations"]:
            for instance in reservation["Instances"]:
                if instance["PrivateDnsName"].startswith(hostname):
                    return instance["InstanceId"]

    def read_env_file(self):
        path = ".env"  # TODO: improve this
        with open(path) as f:
            lines = f.read()
        return lines
