import argparse
import gzip
import logging
import os
import shutil
import subprocess
import sys
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
    '{service_detail_file}': 'service_detail',
    '{date}': 'date',
    '{po_date}': 'podate'
}

data_buckets = [config('GPS_BUCKET_NAME'), config('FILE_196_BUCKET_NAME'), config('TRANSACTION_BUCKET_NAME'),
                config('OP_PROGRAM_BUCKET_NAME'), config("SERVICE_DETAIL_BUCKET_NAME")]
bucket_names = ["gps", "196", "transaction", "op", "service_detail"]


class CommandManager:

    def __init__(self, log, aws_session, general_log_stream, config_file_replacements, config_file_adatrap,
                 debug_state=False):
        self.debug_state = debug_state
        self.logger = log
        self.general_log_stream = general_log_stream
        self.aws_session = aws_session
        self.instance_id = ec2_metadata.instance_id if not self.debug_state else None
        self.config_file_replacements = config_file_replacements

    def send_log_message(self, message, error=False, general=False):
        """
        Send message to logger and cloudwatch logs
        :param message: message to send
        :param error: check if it is an error message
        :param general: send the message to general log
        """
        if not error:
            self.logger.info(message)
            if not self.debug_state:
                self.aws_session.send_log_event(self.instance_id, message)
                if general:
                    self.aws_session.send_log_event(general_log_stream, message)
        else:
            logger.error(message)
            if not self.debug_state:
                self.aws_session.send_log_event(self.instance_id, message)
                message = f"Error en la instancia {self.instance_id}, proceso abortado."
                self.aws_session.send_log_event(general_log_stream, message)
            self.stop_instance()

    def download_file_from_bucket(self, bucket_file, bucket_name):
        """
        Download a file from a bucket
        :param bucket_file: file name
        :param bucket_name: bucket name
        """
        self.send_log_message(f"Bucket encontrado con nombre {bucket_file}")
        self.send_log_message(f"Descargando {bucket_file}...")
        try:
            self.aws_session.download_object_from_bucket(bucket_file, bucket_name, bucket_file)
            self.send_log_message(f"{bucket_file} descargado")
        except ClientError as e:
            self.send_log_message(e, error=True)

    def decompress_file_from_bucket(self, bucket_type, bucket_file):
        """
        Decompress files from bucket
        :param bucket_type: type name bucket
        :param bucket_file: bucket file name
        """
        if bucket_type == "op":
            self.config_file_replacements['{po_path}'] = bucket_file.split('.')[0]
            self.config_file_replacements['{po_date}'] = ''.join(self.config_file_replacements['{po_path}'].split('-'))
            with zipfile.ZipFile(bucket_file, 'r') as zip_ref:
                self.send_log_message(f"Descomprimiendo archivo {bucket_file}...")
                zip_ref.extractall()

                folder = self.config_file_replacements['{po_path}']
                sub_folders = [f.path for f in os.scandir(folder) if f.is_dir()]
                files = [f.path for f in os.scandir(folder) if not f.is_dir()]
                for f in files:
                    with gzip.open(f, 'r') as f_in, open('.'.join(f.split('.')[:2]), 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

                for sub in sub_folders:
                    for f in os.listdir(sub):
                        src = os.path.join(sub, f)
                        with gzip.open(src, 'r') as f_in, open('.'.join(src.split('.')[:2]), 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)

        else:
            self.send_log_message(f"Descomprimiendo archivo {bucket_file}...")
            csv_name = '.'.join(bucket_file.split('.')[:2])
            with gzip.open(bucket_file, 'r') as f_in, open(csv_name, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            if bucket_type == "service_detail":
                self.config_file_replacements['{service_detail_file}'] = csv_name

    def download_and_decompress_data_bucket_files(self, date):
        """
        Download and decompress buckets files with a given date
        :param date: date to check
        """
        for bucket, bucket_name in zip(data_buckets, bucket_names):
            self.send_log_message(f"Buscando datos de {bucket_name}...")
            if not self.aws_session.check_bucket_exists(bucket):
                self.send_log_message(f"El bucket \'{bucket}\' no existe", error=True)
            bucket_file = self.aws_session.get_available_day_for_bucket(date, bucket, bucket_name)
            if bucket_file:
                self.download_file_from_bucket(bucket_file, bucket)
                self.decompress_file_from_bucket(bucket_name, bucket_file)
            else:
                self.send_log_message(
                    f"No se ha encontrado un archivo para la fecha {date} en el bucket asociado a {bucket_name}.",
                    error=True)

    def stop_instance(self):
        """
        Finish the instance and the program
        """
        exit(1)

    def parse_config_file(self, date):
        """
        Parse the config file .par
        :param date: date
        """
        self.send_log_message(f"Generando {date}.par ...")
        self.config_file_replacements['{date}'] = date
        with open(config_file_adatrap, "rt") as f:
            lines = f.read()
            for key, value in self.config_file_replacements.items():
                lines = lines.replace(key, value)
            with open(f"{date}.par", "wt") as f:
                f.write(lines)
        self.send_log_message(f"Archivo {date}.par creado")

    def run_adatrap(self, date):
        self.send_log_message("Ejecutando ADATRAP...")
        if not self.debug_state:
            res = subprocess.run(
                [executable_adatrap, f"{date}.par"],
                capture_output=True,
            )
            std_out = res.stdout.decode("utf-8")
            std_error = res.stderr.decode("utf-8")
            return std_out, std_error
        else:
            return "debug", "debug"
    

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
    session = aws.AWSSession()
    command_manager = CommandManager(logger, session, general_log_stream, config_file_replacements, config_file_adatrap,
                                     debug)

    # Initial Log
    command_manager.send_log_message("Instancia inicializada.")

    # Initialization of ADATRAP
    command_manager.send_log_message("Iniciando proceso ADATRAP...")

    # Download bucket data files
    command_manager.send_log_message("Iniciando descarga de datos para ADATRAP...")
    command_manager.download_and_decompress_data_bucket_files(date)

    # Download ADATRAP .exe
    executable_bucket = config('EXECUTABLES_BUCKET')
    command_manager.send_log_message("Buscando ejecutable ADATRAP...")
    command_manager.download_file_from_bucket(executable_adatrap, executable_bucket)

    # Download config file
    command_manager.send_log_message("Buscando archivo de configuración ADATRAP...")
    command_manager.download_file_from_bucket(config_file_adatrap, executable_bucket)

    # Process config file
    command_manager.parse_config_file(date)

    # Run ADATRAP
    if not debug:
        command_manager.send_log_message("Ejecutando ADATRAP...")
        res = subprocess.run(
            [executable_adatrap, f"{date}.par"],
            capture_output=True,
        )
        # Send ADATRAP Log
        res_message = res.stdout.decode("utf-8")
        if res_message:
            command_manager.send_log_message(res_message)
            # Compress and upload data
            folder_path = os.path.join(data_path, date)
            command_manager.send_log_message("Comprimiendo datos...")
            zip_filename = f"{date}.zip"
            with ZipFile(zip_filename, 'w') as zipObj:
                # Iterate over all the files in directory
                for folder_name, subfolders, filenames in os.walk(folder_path):

                    # except kmls, reportes, debug
                    exception_folders = ["kmls", "reportes", "debug"]
                    if not os.path.split(folder_name)[1] in exception_folders:
                        for filename in filenames:
                            # create conmplete filepath of file in directory
                            file_path = os.path.join(folder_name, filename)
                            # Add file to zip
                            zipObj.write(file_path, basename(file_path))
            command_manager.send_log_message("Compresión de datos exitosa.")

            # Upload to S3
            output_data_bucket = config('OUTPUT_DATA_BUCKET_NAME')
            command_manager.send_log_message(f"Subiendo datos {zip_filename}...")
            if not session.check_bucket_exists(output_data_bucket):
                command_manager.send_log_message(f"El bucket \'{output_data_bucket}\' no existe", error=True)
            try:
                session.send_file_to_bucket(zip_filename, zip_filename, output_data_bucket)
            except ClientError as e:
                command_manager.send_log_message(e)
                command_manager.send_log_message("Error al subir datos.", error=True)

        error_message = res.stderr.decode("utf-8")
        if error_message:
            command_manager.send_log_message(error_message)
        command_manager.send_log_message(f"Proceso ADATRAP para la instancia {command_manager.instance_id} finalizado.",
                                         general=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
