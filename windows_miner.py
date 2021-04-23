import argparse
import logging
import subprocess
import sys

from botocore.exceptions import ClientError
from decouple import config
from ec2_metadata import ec2_metadata

from adatrapMiner import aws

logger = logging.getLogger(__name__)
general_log_stream: str = config("GENERAL_LOG_STREAM")
executable_adatrap: str = 'pvmts_dummy.exe'
config_file_adatrap: str = 'configuration.par'
config_file_replacements: dict = {
    'op_path': 'op_path_replacement',
    'day_type': 'LABORAL',
    'service_detail_file': 'Diccionario-DetalleServicioZP_20201116_20201130v2.csv',
    'date': 'date'
}

def main(argv):
    """
    Script to execute ADATRAP
    """

    logging.basicConfig(level=logging.INFO)

    # Arguments and description
    parser = argparse.ArgumentParser(description="Script to execute ADATRAP")
    parser.add_argument("date", help="Date to execute adatrap")
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument("-d", "--debug", help="Debug mode to test functions without instance", action="store_true" )
    args = parser.parse_args(argv[1:])
    date = args.date
    debug = args.debug
    path = config("ADATRAP_PATH")

    # Initial Log
    session = aws.AWSSession()
    if not debug:
        instance_id = ec2_metadata.instance_id

    def send_log_message(message, error=False):
        if not debug:
            if not error:
                logger.info(message)
            else:
                logger.error(message)
            session.send_log_event(instance_id, message)

    send_log_message("Instancia inicializada.")

    # Initialization of ADATRAP
    send_log_message("Iniciando proceso ADATRAP...")

    # Download files TODO

    # Download executable
    send_log_message("Descargando ejecutable ADATRAP...")
    bucket_name = config('EXECUTABLES_BUCKET')
    if not session.check_bucket_exists(bucket_name):
        send_log_message(f"'Bucket \'{bucket_name}\' does not exist", error=True)
        exit(1)
    try:
        session.download_object_from_bucket(executable_adatrap, bucket_name, executable_adatrap)
    except ClientError as e:
        send_log_message(e, error=True)
        exit(1)
    send_log_message('Ejecutable ADATRAP descargado.')

    # Download config file
    send_log_message("Descargando archivo de configuración ADATRAP...")
    try:
        session.download_object_from_bucket(config_file_adatrap, bucket_name, config_file_adatrap)
    except ClientError as e:
        send_log_message(e, error=True)
        exit(1)
    send_log_message('Archivo de configuración ADATRAP descargado.')

    # Process config file
    config_file_replacements['date'] = date

    with open(config_file_adatrap, "rt") as f:
        lines = f.read()
        for key, value in config_file_replacements.items():
            lines = lines.replace(key, value)
        with open(f"{date}.par", "wt") as f:
            f.write(lines)

    # Run ADATRAP
    res = subprocess.run(
        ["pivots_dummy.exe", f"{date}.par"],
        capture_output=True,
    )
    # Send ADATRAP Log
    res_message = res.stdout.decode("utf-8")
    if res_message:
        send_log_message(res_message)
    error_message = res.stderr.decode("utf-8")
    if error_message:
        send_log_message(error_message)
    send_log_message("Proceso ADATRAP finalizado.")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
