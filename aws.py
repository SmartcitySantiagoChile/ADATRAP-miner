import datetime
import os
import time
import urllib

import boto3
import botocore
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

    # EC2 methods

    def create_key_pair(self, name: str = "ec2-keypair") -> None:
        """
        Create a key_pair with given name (ec2-keypair default).
        The ec2-keypair.pem file will be saved at root folder.
        """
        ec2 = self.session.resource("ec2")
        with open(f"{os.path.join('tmp',name)}.pem", "w") as outfile:
            key_pair = ec2.create_key_pair(KeyName=name)
            key_pair_out = str(key_pair.key_material)
            outfile.write(key_pair_out)

    def run_ec2_instance(self, date: str) -> dict:
        """
        Create an EC2 instance and next run a given command
        :return: instance id
        """
        ec2 = self.session.client("ec2")
        env_file = self._read_env_file()
        with open('windows_script') as f:
            lines = f.read()
            lines = lines.replace('{EC2_DATE}', date).replace("{ENV_DATA}",
                                                              env_file).replace("{GROUP_NAME}",
                                                                                config('LOG_GROUP'))
            script = lines
            # TODO: make this configurable
            instances = ec2.run_instances(
                ImageId=config("AMI_ID"),
                MinCount=1,
                MaxCount=1,
                InstanceType=config("INSTANCE_TYPE"),
                KeyName=os.path.join('tmp', config("KEY_PAIR")),
                UserData=script,
                Monitoring={"Enabled": True},
            )
        return instances

    def stop_ec2_instance(self, instance_id: str):
        """
        Finish ec2 instance with given id
        :return: instance id
        """
        ec2 = self.session.resource("ec2")
        instance = ec2.Instance(instance_id)
        return instance.terminate()

    def _read_env_file(self):
        """
        Read a .env file and add \n at start
        :return: .env file with \n at start
        """
        path = ".env"  # TODO: improve this
        with open(path) as f:
            lines = "\n" + f.read()
        return lines

    # Cloudwatch methods
    def get_log_stream(self, log_group_name: str, log_stream_name: str, start_date: str, end_date: str) -> list:
        logs = self.session.client("logs")
        formatted_start_date = datetime.date.fromisoformat(start_date)
        formatted_start_time = datetime.datetime.combine(formatted_start_date,
                                                         datetime.datetime.min.time())
        formatted_start_time = int(formatted_start_time.timestamp())
        formatted_end_date = datetime.date.fromisoformat(end_date)
        formatted_end_time = datetime.datetime.combine(formatted_end_date, datetime.datetime.min.time()).timestamp()

        response = logs.get_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name,
            startTime=formatted_start_time,
        )
        return response['events']

    def create_log_stream(self, name: str) -> None:
        """
        Create a Log Stream with given name
        :param name: name of the Log Stream
        """
        logs = self.session.client("logs")
        logs.create_log_stream(logGroupName=self.log_group, logStreamName=name)

    def send_log_event(self, log_stream_name: str, message: str, status: str) -> dict:
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
                    "message": f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{status}{message}",
                }
            ],
        }
        if token:
            args["sequenceToken"] = token
        response = logs.put_log_events(**args)
        return response

    def get_last_token_event(self, log_stream_name: str) -> str:
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

    def create_log_group(self, group_name: str, retention: int = 7) -> dict:
        """
        Create log group with a given game and retention (in days)
        :param group_name: name of the log group
        :param retention: retention of logs in days
        :return: log response
        """
        logs = self.session.client("logs")
        response = logs.create_log_group(
            logGroupName=group_name,
        )
        logs.put_resource_policy(policyName="string", policyDocument="string")
        logs.put_retention_policy(logGroupName=group_name, retentionInDays=retention)
        return response

    # S3 methods

    def retrieve_obj_list(self, bucket_name):
        s3 = self.session.resource('s3')
        bucket = s3.Bucket(bucket_name)

        obj_list = []
        for obj in bucket.objects.all():
            size_in_mb = float(obj.size) / (1024 ** 2)
            size_in_mb = float(obj.size) / (1024 ** 2)
            url = self._build_url(obj.key, bucket_name)
            obj_list.append(dict(name=obj.key, size=size_in_mb, last_modified=obj.last_modified, url=url))

        return obj_list

    def _build_url(self, key, bucket_name):
        return ''.join(['https://s3.amazonaws.com/', bucket_name, '/', urllib.parse.quote(key)])

    def check_bucket_exists(self, bucket_name):
        s3 = self.session.resource('s3')
        try:
            s3.meta.client.head_bucket(Bucket=bucket_name)
            return True
        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response['Error']['Code'])
            if error_code == 403:
                raise ValueError("Private Bucket. Forbidden Access!")
            elif error_code == 404:
                return False

    def check_file_exists(self, bucket_name, key):
        s3 = self.session.resource('s3')
        try:
            s3.Object(bucket_name, key).load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                # The object does not exist.
                return False
            else:
                # Something else has gone wrong.
                raise ValueError(e.response['Error'])
        else:
            # The object exists.
            return True

    def download_object_from_bucket(self, obj_key, bucket_name, file_path):
        s3 = self.session.resource('s3')
        bucket = s3.Bucket(bucket_name)
        bucket.download_file(obj_key, file_path)

    def get_available_day_for_bucket(self, date, bucket_name, bucket_type) -> str:
        """
        Check available days in bucket and compare with given date
        :param bucket_type:
        :param date: date to check
        :param bucket_name: name of the bucket
        :return: name of matched bucket
        """
        available_bucket_days = [files['name'] for files in self.retrieve_obj_list(bucket_name)]
        if bucket_type == "op":
            return self._get_available_day_for_op_bucket(available_bucket_days, date)
        elif bucket_type == "service_detail":
            return self._get_available_day_for_service_detail_bucket(available_bucket_days, date)
        else:
            day = [day for day in available_bucket_days if date in day]
            return day[0] if day else None

    def _get_available_day_for_op_bucket(self, available_bucket_days, date):
        """
        Check conditions of date's availability for a given op date list
        :param available_bucket_days: date list for op date
        :param date: date to check
        """
        available_bucket_days = [datetime.date.fromisoformat(day.split('.')[0]) for day in available_bucket_days]
        available_bucket_days.sort()
        date = datetime.date.fromisoformat(date)
        if date < available_bucket_days[0]:
            return None
        valid_date = available_bucket_days[0]
        for available_day in available_bucket_days[1:]:
            if available_day <= date:
                valid_date = available_day
        return f"{valid_date.isoformat()}.po.zip"

    def send_file_to_bucket(self, file_path, file_key, bucket_name):
        s3 = self.session.resource('s3')
        bucket = s3.Bucket(bucket_name)
        bucket.upload_file(file_path, file_key)

        return self._build_url(file_key, bucket_name)

    def send_object_to_bucket(self, obj, obj_key, bucket_name):
        s3 = self.session.resource('s3')
        bucket = s3.Bucket(bucket_name)
        bucket.upload_fileobj(obj, obj_key)
        s3.Object(bucket_name, obj_key).Acl().put(ACL='public-read')

    # EC2 inside instance methods

    def get_instance_id(self) -> str:
        """
        Get the current instance id (only works inside of an EC2 Instance)
        :return: instance id
        """
        import socket

        hostname = socket.gethostname()
        session = self.session.client("ec2")
        for reservation in session.describe_instances()["Reservations"]:
            for instance in reservation["Instances"]:
                if instance["PrivateDnsName"].startswith(hostname):
                    return instance["InstanceId"]

    def _get_available_day_for_service_detail_bucket(self, available_bucket_days, date):
        """
        Check conditions of date's availability for a given service detail list
        :param available_bucket_days: date list files for service detail
        :param date: date to check
        """
        formatted_available_bucket_days = [day.split(".")[0].split("_")[1:] for day in available_bucket_days]

        def date_to_iso_format(date):
            return datetime.date.fromisoformat(f"{date[:4]}-{date[4:6]}-{date[6:8]}")

        formatted_available_bucket_days = [[date_to_iso_format(days[0]), date_to_iso_format(days[1])] for days in
                                           formatted_available_bucket_days]
        formatted_available_bucket_days.sort()
        date = datetime.date.fromisoformat(date)
        for i in range(len(formatted_available_bucket_days)):
            start_date = formatted_available_bucket_days[i][0]
            end_date = formatted_available_bucket_days[i][1]
            if start_date <= date <= end_date:
                return available_bucket_days[i]
        return None
