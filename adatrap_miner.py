import logging

import botocore
import click
from decouple import config

import aws


@click.group()
@click.pass_context
def cli(context):
    """Adatrap Miner: manage ec2 instances to automaticaly process ADATRAP data."""
    context.ensure_object(dict)
    context.obj['logger'] = logging.getLogger(__name__)
    context.obj['general_log_stream'] = config("GENERAL_LOG_STREAM")
    context.obj['session'] = aws.AWSSession()
    logging.basicConfig(level=logging.INFO)



@cli.command()
@click.pass_context
def create_key_par(context):
    """Create key par to use with EC2 instances."""
    context = context.obj
    try:
        context['session'].create_key_pair()
        message = "¡Keypair creado exitosamente! El archivo ec2-keypair.pem se encuentra en la raíz del proyecto."
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message)
    except botocore.exceptions.ClientError:
        message = "El keypair 'ec2-keypair' ya existe."
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
