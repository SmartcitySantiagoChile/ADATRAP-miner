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
        self.job_queue = config("JOB_QUEUE")
        self.job_definition = config("JOB_DEFINITION")
        self.client = self.session.client("batch")

    def submit_job(self, job_name, command):
        response = self.client.submit_job(
            jobName=job_name,
            jobQueue=self.job_queue,
            jobDefinition=self.job_definition,
            parameters={"name": job_name},
            containerOverrides={
                "command": command,
            },
            propagateTags=True,
        )
        return response
