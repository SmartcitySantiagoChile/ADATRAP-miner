import argparse
import glob
import gzip
import logging
import os
import shutil
import subprocess
import sys
import time
import zipfile
from os.path import basename
from zipfile import ZipFile

from botocore.exceptions import ClientError
from decouple import config
from ec2_metadata import ec2_metadata

import aws

logger = logging.getLogger(__name__)
data_path: str = "ADATRAP"
general_log_stream: str = config("GENERAL_LOG_STREAM")
executable_adatrap: str = 'pvmtsc_v0.1.exe'
config_file_adatrap: str = 'pvmtsc_v0.1.par'
config_file_replacements: dict = {
    '{po_path}': 'op_path_replacement',
    'day_type': 'LABORAL',  # TODO: check
    '{service_detail_file}': 'service_detail',
    '{date}': 'date',
    '{po_date}': 'podate'
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
    parser.add_argument("-d", "--debug", help="Debug mode to tests functions without instance", action="store_true")
    args = parser.parse_args(argv[1:])
    date = args.date
    debug = args.debug

    # Initial Log
    session = aws.AWSSession()
    if not debug:
        instance_id = ec2_metadata.instance_id

    def send_log_message(message, error=False, general=False):
        if not error:
            logger.info(message)
            if not debug:
                session.send_log_event(instance_id, message)
                if general:
                    session.send_log_event(general_log_stream, message)
        else:
            logger.error(message)
            if not debug:
                session.send_log_event(instance_id, message)
                message = f"Error en la instancia {instance_id}, proceso abortado."
                session.send_log_event(general_log_stream, message)
            exit(1)

    send_log_message("Instancia inicializada.")

    # Initialization of ADATRAP
    send_log_message("Iniciando proceso ADATRAP...")

    # Download files
    send_log_message("Iniciando descarga de datos para ADATRAP...")

    # Download data buckets
    data_buckets = [config('GPS_BUCKET_NAME'), config('FILE_196_BUCKET_NAME'), config('TRANSACTION_BUCKET_NAME'),
                    config('OP_PROGRAM_BUCKET_NAME'), config("SERVICE_DETAIL_BUCKET_NAME")]
    bucket_names = ["gps", "196", "transaction", "op", "service_detail"]
    for bucket, bucket_name in zip(data_buckets, bucket_names):
        send_log_message(f"Buscando datos de {bucket_name}...")
        if not session.check_bucket_exists(bucket):
            send_log_message(f"El bucket \'{bucket}\' no existe", error=True)
        bucket_file = session.get_available_day_for_bucket(date, bucket, bucket_name)
        if bucket_file:
            send_log_message(f"Bucket encontrado con nombre {bucket_file}")
            send_log_message(f"Descargando {bucket_file}...")
            try:
                session.download_object_from_bucket(bucket_file, bucket, bucket_file)
            except ClientError as e:
                send_log_message(e, error=True)

            if bucket_name == "op":
                config_file_replacements['{po_path}'] = bucket_file.split('.')[0]
                config_file_replacements['{po_date}'] = ''.join(config_file_replacements['{po_path}'].split('-'))
                with zipfile.ZipFile(bucket_file, 'r') as zip_ref:
                    service_detail_path = config_file_replacements['{po_path}']
                    send_log_message(f"Descomprimiendo archivo {bucket_file}...")
                    zip_ref.extractall()

                    folder = config_file_replacements['{po_path}']
                    subfolders = [f.path for f in os.scandir(folder) if f.is_dir()]
                    files = [f.path for f in os.scandir(folder) if not f.is_dir()]
                    for f in files:
                        with gzip.open(f, 'r') as f_in, open('.'.join(f.split('.')[:2]), 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    for sub in subfolders:
                        for f in os.listdir(sub):
                            src = os.path.join(sub, f)
                            with gzip.open(src, 'r') as f_in, open('.'.join(src.split('.')[:2]), 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)

            else:
                send_log_message(f"Descomprimiendo archivo {bucket_file}...")
                csv_name = '.'.join(bucket_file.split('.')[:2])
                with gzip.open(bucket_file, 'r') as f_in, open(csv_name, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                if bucket_name == "service_detail":
                    config_file_replacements['{service_detail_file}'] = csv_name
                    print(csv_name)
        else:
            send_log_message(
                f"No se ha encontrado un archivo para la fecha {date} en el bucket asociado a {bucket_name}.",
                error=True)

    # Download executable
    send_log_message("Descargando ejecutable ADATRAP...")
    executable_bucket = config('EXECUTABLES_BUCKET')
    if not session.check_bucket_exists(executable_bucket):
        send_log_message(f"'Bucket \'{executable_bucket}\' does not exist", error=True)
    try:
        session.download_object_from_bucket(executable_adatrap, executable_bucket, executable_adatrap)
    except ClientError as e:
        send_log_message(e, error=True)
    send_log_message('Ejecutable ADATRAP descargado.')

    # Download config file
    send_log_message("Descargando archivo de configuración ADATRAP...")
    try:
        session.download_object_from_bucket(config_file_adatrap, executable_bucket, config_file_adatrap)
    except ClientError as e:
        send_log_message(e, error=True)
        exit(1)
    send_log_message('Archivo de configuración ADATRAP descargado.')

    # Process config file
    config_file_replacements['{date}'] = date
    with open(config_file_adatrap, "rt") as f:
        lines = f.read()
        for key, value in config_file_replacements.items():
            lines = lines.replace(key, value)
        with open(f"{date}.par", "wt") as f:
            f.write(lines)

    # Run ADATRAP
    if not debug:
        send_log_message("Ejecutando ADATRAP...")
        res = subprocess.run(
            [executable_adatrap, f"{date}.par"],
            capture_output=True,
        )
        # Send ADATRAP Log
        res_message = res.stdout.decode("utf-8")
        if res_message:
            send_log_message(res_message)
            # Compress and upload data
            folder_path = os.path.join(data_path, date)
            send_log_message("Comprimiendo datos...")
            zip_filename = f"{date}.zip"
            with ZipFile(zip_filename, 'w') as zipObj:
                # Iterate over all the files in directory
                for folder_name, subfolders, filenames in os.walk(folder_path):
                    for filename in filenames:
                        # create conmplete filepath of file in directory
                        file_path = os.path.join(folder_name, filename)
                        # Add file to zip
                        zipObj.write(file_path, basename(file_path))

            # Upload to S3
            # data_bucket = config('DATA_BUCKET_NAME')
            # if not session.check_bucket_exists(data_bucket):
            #     send_log_message(f"El bucket \'{data_bucket}\' no existe", error=True)
            #     exit(1)
            #
            # def send_file_to_s3(matched_file, filename):
            #     send_log_message('{0}: cargando archivo {1}'.format(datetime.now().replace(microsecond=0), matched_file))
            #     session.send_file_to_bucket(matched_file, filename, bucket_name)
            #     send_log_message('{0}: carga de archivo {1} finalizada'.format(datetime.now().replace(microsecond=0), matched_file))
            #
            # try:
            #     file_exists = session.check_file_exists(data_bucket, zip_filename)
            #     if not file_exists:
            #         send_file_to_s3(matched_file, filename)
            #         continue
            #
            #     if replace:
            #         send_file_to_s3(matched_file, filename)
            #     elif ignore_if_exists:
            #         continue
            #     else:
            #         answer = input('file \'{0}\' exists in bucket. Do you want to replace it? (y/n): '.format(filename))
            #         if answer not in ['y', 'Y']:
            #             print('file {0} was not replaced'.format(filename))
            #             continue
            #         send_file_to_s3(matched_file, filename)
            # except ClientError as e:
            #     # ignore it and continue uploading files
            #     print(e)

        error_message = res.stderr.decode("utf-8")
        if error_message:
            send_log_message(error_message)
        send_log_message(f"Proceso ADATRAP para la instancia {instance_id} finalizado.", general=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
