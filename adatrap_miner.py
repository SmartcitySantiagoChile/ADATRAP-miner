import logging

import botocore
import click
from decouple import config, UndefinedValueError

import aws


def check_env_variables():
    env_dict = {
        "AWS_ACCESS_KEY_ID": "Id de acceso a AWS",
        "AWS_SECRET_ACCESS_KEY": "Clave de acceso a AWS",
        "REGION_NAME": "Region de acceso a AWS",
        "AMI_ID": "Id de AMI (Amazon Machine Image) a utilizar",
        "KEY_PAIR": "Par de claves de acceso a EC2 AWS",
        "LOG_GROUP": "Nombre de log de grupo Cloudwatch",
        "GENERAL_LOG_STREAM": "Nombre del log stream general de Cloudwatch",
        "EXECUTABLES_BUCKET": "Bucket S3 que contiene el ejecutable y configurable ADATARP",
        "GPS_BUCKET_NAME": "Bucket S3 que contiene datos de gps",
        "OP_PROGRAM_BUCKET_NAME": "Bucket S3 que contiene datos de programas de operación",
        "FILE_196_BUCKET_NAME": "Bucket S3 que contiene datos 196",
        "TRANSACTION_BUCKET_NAME": "Bucket S3 que contiene datos de transacciones",
        "DATA_BUCKET_NAME": "Bucket S3 donde se almacenan los resultados de ADATRAP"
    }
    for key, answer in env_dict.items():
        try:
            name = config(key)
        except UndefinedValueError:
            logging.getLogger(__name__).error(f"Variable {key} ({answer}) no definida en .env")
            exit(1)


@click.group()
@click.pass_context
def cli(context):
    """Adatrap Miner: manage ec2 instances to automaticaly process ADATRAP data."""
    context.ensure_object(dict)
    context.obj['logger'] = logging.getLogger(__name__)
    check_env_variables()
    context.obj['general_log_stream'] = config("GENERAL_LOG_STREAM")
    context.obj['session'] = aws.AWSSession()
    logging.basicConfig(level=logging.INFO)


@cli.command()
@click.argument('name', nargs=-1)
@click.pass_context
def create_key_pair(context, name) -> None:
    """Create key pair to use with EC2 instances.

    NAME (optional) is the name of the key pair
    """
    context = context.obj
    name = "ec2-keypair" if not name else name[0]
    try:
        context['session'].create_key_pair(name)
        message = f"¡Keypair creado exitosamente! El archivo '{name}.pem' se encuentra en la raíz del proyecto."
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message)
    except botocore.exceptions.ClientError:
        message = f"El keypair '{name}' ya existe."
        context['logger'].error(message)
        context['session'].send_log_event(context['general_log_stream'], message)


@cli.command()
@click.argument('date')
@click.pass_context
def create_ec2_instance(context, date) -> None:
    """
    Create an ec2 instance with windows miner.

    DATE is the date to process in the ec2 instance
    """
    context = context.obj
    try:
        status = context['session'].run_ec2_instance(date)
        instance_id = status["Instances"][0]["InstanceId"]
        message = f"Instancia creada con id: {instance_id} para el día {date}"
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message)

        # Create EC2 Log Stream
        context['session'].create_log_stream(instance_id)
        message = f"Log Stream creado con nombre: {instance_id}"
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message)

        # Send initial message to EC2 Log Stream
        message = "Instancia creada correctamente."
        context['session'].send_log_event(instance_id, message)
    except botocore.exceptions.ClientError:
        message = f"No se pudo crear instancia con fecha {date}."
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message)


@cli.command()
@click.argument('instance_id')
@click.pass_context
def stop_ec2_instance(context, instance_id) -> None:
    """
    Stop an ec2 instance with a given id.

    ID is the id of the ec2 instance
    """
    context = context.obj
    message = f"Finalizando instancia con id {instance_id}..."
    context['logger'].info(message)
    context['session'].send_log_event(context['general_log_stream'], message)
    try:
        context['session'].stop_ec2_instance(instance_id)
        message = f"Instancia con id {instance_id} finalizada."
        context['logger'].info(message)
    except botocore.exceptions.ClientError:
        message = f"No se pudo terminar instancia con id {instance_id}, id inválido."
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message)

