import argparse
import logging
import sys

from botocore.exceptions import ClientError
from decouple import config
from ec2_metadata import ec2_metadata

from adatrapMiner import aws

logger = logging.getLogger(__name__)
general_log_stream: str = config("GENERAL_LOG_STREAM")
executable_adatrap: str = 'pvmts_dummy.exe'


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
    args = parser.parse_args(argv[1:])
    date = args.date
    path = config("ADATRAP_PATH")

    # Initial Log
    session = aws.AWSSession()
    instance_id = ec2_metadata.instance_id

    def send_log_message(message):
        logger.info(message)
        session.send_log_event(instance_id, message)

    send_log_message("Instancia inicializada.")

    # # Initialization of ADATRAP
    send_log_message("Iniciando proceso ADATRAP...")

    # # Download executable
    send_log_message("Descargando ejecutable ADATRAP...")
    bucket_name = config('EXECUTABLES_BUCKET')
    if not session.check_bucket_exists(bucket_name):
        send_log_message(f"'Bucket \'{bucket_name}\' does not exist")
        exit(1)
    try:
        session.download_object_from_bucket(executable_adatrap, bucket_name, executable_adatrap)
    except ClientError as e:
        send_log_message(e)
    send_log_message('Ejecutable ADATRAP descargado.')

    # # Run ADATRAP
    # res = subprocess.run(
    #     ["pvmts_dummy.exe", f"{date}.par"],
    #     capture_output=True,
    # )
    # # Send ADATRAP Log
    # res_message = res.stdout.decode("utf-8")
    # if res_message:
    #     send_log_message(res_message)
    # error_message = res.stderr.decode("utf-8")
    # if error_message:
    #     send_log_message(error_message)
    # send_log_message("Proceso ADATRAP finalizado.")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
