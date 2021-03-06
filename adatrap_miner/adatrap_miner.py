import logging
import os
from datetime import datetime

import botocore
import click
from decouple import UndefinedValueError
from decouple import config

from adatrap_miner import aws
from adatrap_miner import windows_manager


def check_env_variables():
    env_dict = {
        "AWS_ACCESS_KEY_ID": "Id de acceso a AWS",
        "AWS_SECRET_ACCESS_KEY": "Clave de acceso a AWS",
        "REGION_NAME": "Region de acceso a AWS",
        "AMI_ID": "Id de AMI (Amazon Machine Image) a utilizar",
        "INSTANCE_TYPE": "Máquina EC2 a utilizar",
        "KEY_PAIR": "Par de claves de acceso a EC2 AWS",
        "LOG_GROUP": "Nombre de log de grupo Cloudwatch",
        "GENERAL_LOG_STREAM": "Nombre del log stream general de Cloudwatch",
        "EXECUTABLES_BUCKET": "Bucket S3 que contiene el ejecutable y configurable ADATARP",
        "GPS_BUCKET_NAME": "Bucket S3 que contiene datos de gps",
        "OP_PROGRAM_BUCKET_NAME": "Bucket S3 que contiene datos de programas de operación",
        "FILE_196_BUCKET_NAME": "Bucket S3 que contiene datos 196",
        "TRANSACTION_BUCKET_NAME": "Bucket S3 que contiene datos de transacciones",
        "OUTPUT_DATA_BUCKET_NAME": "Bucket S3 donde se almacenan los resultados de ADATRAP",
        "SERVICE_DETAIL_BUCKET_NAME": "Bucket S3 donde se almacenan los archivos de detalle de servicio",
        "EXECUTABLE_VERSION": "Versión de ejecutable ADATRAP"
    }
    for key, answer in env_dict.items():
        try:
            name = config(key)
            if not name:
                raise UndefinedValueError
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
    except botocore.exceptions.ClientError:
        message = f"El keypair '{name}' ya existe."
        context['logger'].info(message)


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
        message_status = "INFO: "
        message = f"Creando instancia para el día {date}..."
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message, message_status)
        status = context['session'].run_ec2_instance(date)
        instance_id = status["Instances"][0]["InstanceId"]
        message = f"Instancia creada con id: {instance_id} para el día {date}"
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message, message_status)

        # Create EC2 Log Stream
        message = f"Creando log stream para instancia {instance_id}..."
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message, message_status)
        context['session'].create_log_stream(instance_id)
        message = f"Log Stream creado con nombre: {instance_id}"
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message, message_status)

        # Send initial message to EC2 Log Stream
        message = "Instancia creada correctamente."
        context['session'].send_log_event(instance_id, message, message_status)

    except botocore.exceptions.ClientError as e:
        message_status = "ERROR: "
        context['logger'].info(e)
        context['session'].send_log_event(context['general_log_stream'], e, message_status)
        message = f"No se pudo crear instancia con fecha {date}."
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message, message_status)


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
    status = "INFO: "
    context['logger'].info(message)
    context['session'].send_log_event(context['general_log_stream'], message, status)
    try:
        context['session'].stop_ec2_instance(instance_id)
        message = f"Instancia con id {instance_id} finalizada."
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message, status)
    except botocore.exceptions.ClientError:
        status = "ERROR: "
        message = f"No se pudo terminar instancia con id {instance_id}, id inválido."
        context['logger'].info(message)
        context['session'].send_log_event(context['general_log_stream'], message, status)
    except Exception as e:
        status = "ERROR: "
        context['logger'].info(e)
        context['session'].send_log_event(context['general_log_stream'], e, status)


@cli.command()
@click.pass_context
@click.argument('log_name')
@click.option('-e', '--end_date', 'end_date', help='end date to search logs (YYYY-MM-DD).')
@click.option('-s', '--start_date', 'start_date', help='start date to search logs (YYYY-MM-DD).')
@click.option('-o', '--output', 'output', help='filename to save log.')
def get_log_stream(context, output, start_date, end_date, log_name) -> None:
    """
    Get logs stream from a given name and given date.

    LOG_STREAM_NAME is the name of the log stream.

    """
    start_date = "2000-01-01" if not start_date else start_date
    end_date = datetime.now().strftime("%Y-%m-%d") if not end_date else end_date
    context = context.obj
    message = f"Obteniendo últimos logs..."
    context['logger'].info(message)
    try:
        log_events = context['session'].get_log_stream(config('LOG_GROUP'), log_name,
                                                       start_date=start_date, end_date=end_date)
    except botocore.exceptions.ClientError:
        message = f"No se pueden obtener los logs generales."
        context['logger'].error(message)
        exit(1)

    if output:
        with open(f"{output}.log", 'w') as l:
            for event in log_events:
                l.write(event["message"].replace("\n", "") + '\n')
        message = f"Logs almacenados exitosamente en {output}.log "
        context['logger'].info(message)
    else:
        for event in log_events:
            if "INFO" in event['message']:
                context['logger'].info(event['message'])
            else:
                context['logger'].error(event['message'])


@cli.command()
@click.pass_context
@click.argument('date')
@click.option('-d', '--debug/--no-debug', 'debug', help='debug mode (works on UNIX).', default=False)
def execute_adatrap(context, date, debug):
    """
    Execute adatrap program. (Works only in Windows)

    DATE is the date to process.

    """
    # set variables
    context = context.obj
    data_path: str = "ADATRAP"
    general_log_stream: str = context["general_log_stream"]
    executable_adatrap: str = f"pvmtsc_v{config('EXECUTABLE_VERSION')}.exe"
    config_file_adatrap: str = f"pvmtsc_v{config('EXECUTABLE_VERSION')}.par"
    config_file_replacements: dict = {
        '{po_path}': 'op_path_replacement',
        '{service_detail_file}': 'service_detail',
        '{date}': 'date',
        '{po_date}': 'podate'
    }

    data_buckets = [config("SERVICE_DETAIL_BUCKET_NAME"), config('GPS_BUCKET_NAME'), config('FILE_196_BUCKET_NAME'), config('TRANSACTION_BUCKET_NAME'),
                    config('OP_PROGRAM_BUCKET_NAME')]
    bucket_names = ["service_detail", "gps", "196", "transaction", "op"]

    command_manager = windows_manager.WindowsManager(context["logger"], context['session'], general_log_stream,
                                                     config_file_replacements,
                                                     os.path.join("tmp", config_file_adatrap), data_path, data_buckets, bucket_names,
                                                     os.path.join("tmp", executable_adatrap), debug)

    # Initial Log
    command_manager.send_log_message("Instancia inicializada.")

    # Initialization of ADATRAP
    command_manager.send_log_message("Iniciando proceso ADATRAP...")


    # Download ADATRAP .exe
    executable_bucket = config('EXECUTABLES_BUCKET')
    command_manager.send_log_message("Buscando ejecutable ADATRAP...")
    command_manager.download_file_from_bucket(executable_adatrap, executable_bucket)

    # Download config file
    command_manager.send_log_message("Buscando archivo de configuración ADATRAP...")
    command_manager.download_file_from_bucket(config_file_adatrap, executable_bucket)

    # Download bucket data files
    command_manager.send_log_message("Iniciando descarga de datos para ADATRAP...")
    command_manager.download_and_decompress_data_bucket_files(date)

    # Process config file
    command_manager.parse_config_file(date)

    # Run ADATRAP
    stdout, stderr = command_manager.run_adatrap(date)
    if stdout:
        for message in stdout.split("\n"):
            command_manager.send_log_message(f"Ejecutable ADATRAP - {message}")

        # Compress output data
        command_manager.compress_adatrap_data(date)
        output_file_name = f"{date}.zip"

        # Upload to S3
        command_manager.upload_output_data_to_s3(output_file_name)
        command_manager.send_log_message(f"Proceso ADATRAP para la instancia {command_manager.instance_id} finalizado.",
                                         general=True)
    if stderr:
        command_manager.send_log_message(f"Proceso ADATRAP para la instancia {command_manager.instance_id} finalizado con errores.",
                                         general=True, error=True)
        command_manager.send_log_message(stderr, general=True, error=True)

    command_manager.stop_instance()
