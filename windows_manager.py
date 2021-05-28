import gzip
import os
import shutil
import subprocess
import zipfile
from os.path import basename
from zipfile import ZipFile

from botocore.exceptions import ClientError
from decouple import config
from ec2_metadata import ec2_metadata


class WindowsManager:

    def __init__(self, log, aws_session, general_log_stream, config_file_replacements, config_file_adatrap, data_path
                 , data_buckets, bucket_names, executable_adatrap, debug_state=False):
        self.debug_state = debug_state
        self.logger = log
        self.general_log_stream = general_log_stream
        self.aws_session = aws_session
        self.instance_id = ec2_metadata.instance_id if not self.debug_state else None
        self.config_file_replacements = config_file_replacements
        self.config_file_adatrap = config_file_adatrap
        self.data_path = data_path
        self.data_buckets = data_buckets
        self.buckets_name = bucket_names
        self.executable_adatrap = executable_adatrap
        self.tmp_files_path = "tmp"

    def send_log_message(self, message, error=False, general=False):
        """
        Send message to logger and cloudwatch logs
        :param message: message to send
        :param error: check if it is an error message
        :param general: send the message to general log
        """
        if not error:
            status = "INFO: "
            self.logger.info(message)
            if not self.debug_state:
                self.aws_session.send_log_event(self.instance_id, message, status)
                if general:
                    self.aws_session.send_log_event(self.general_log_stream, message, status)
        else:
            status = "ERROR: "
            self.logger.error(message)
            if not self.debug_state:
                self.aws_session.send_log_event(self.instance_id, message, status)
                self.aws_session.send_log_event(self.general_log_stream, message, status)
                message = f"Error en la instancia {self.instance_id}, proceso abortado."
                self.aws_session.send_log_event(self.instance_id, message, status)
                self.aws_session.send_log_event(self.general_log_stream, message, status)
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
            self.aws_session.download_object_from_bucket(bucket_file, bucket_name,
                                                         os.path.join(self.tmp_files_path, bucket_file))
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
                zip_ref.extractall(self.tmp_files_path)

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
        for bucket, bucket_name in zip(self.data_buckets, self.buckets_name):
            self.send_log_message(f"Buscando datos de {bucket_name}...")
            if not self.aws_session.check_bucket_exists(bucket):
                self.send_log_message(f"El bucket \'{bucket}\' no existe", error=True)
            bucket_file = self.aws_session.get_available_day_for_bucket(date, bucket, bucket_name)
            if bucket_file:
                self.download_file_from_bucket(bucket_file, bucket)
                self.decompress_file_from_bucket(bucket_name, os.path.join(self.tmp_files_path, bucket_file))
            else:
                self.send_log_message(
                    f"No se ha encontrado un archivo para la fecha {date} en el bucket asociado a {bucket_name}.",
                    error=True)

    def stop_instance(self):
        """
        Finish the instance and the program
        """
        status = "INFO: "
        message = f"Finalizando instancia {self.instance_id} ..."
        self.aws_session.send_log_event(self.general_log_stream, message, status)
        self.aws_session.send_log_event(self.instance_id, message, status)
        self.aws_session.stop_ec2_instance(self.instance_id)
        message = f"Instancia {self.instance_id} finalizada."
        self.aws_session.send_log_event(self.instance_id, message, status)
        self.aws_session.send_log_event(self.general_log_stream, message, status)
        exit(1)

    def parse_config_file(self, date):
        """
        Parse the config file .par
        :param date: date
        """
        self.send_log_message(f"Generando {date}.par ...")
        self.config_file_replacements['{date}'] = date
        with open(self.config_file_adatrap, "rt") as f:
            lines = f.read()
            for key, value in self.config_file_replacements.items():
                lines = lines.replace(key, value)
            with open(f"{date}.par", "wt") as f:
                f.write(lines)
        self.send_log_message(f"Archivo {date}.par creado")

    def run_adatrap(self, date):
        """
        Run adatrap executable with 1:15 [h] timeout
        :param date: date to execute
        :return: stdout and stderr from adatrap executable
        """
        self.send_log_message("Ejecutando ADATRAP...")
        if not self.debug_state:
            try:
                res = subprocess.run(
                    [self.executable_adatrap, f"{date}.par"],
                    capture_output=True, timeout=4500
                )
                std_out = res.stdout.decode("utf-8")
                std_error = res.stderr.decode("utf-8")
                return std_out, std_error
            except subprocess.TimeoutExpired:
                self.send_log_message("Proceso ADATRAP no terminó su ejecución luego de 1:15.", error=True)
        else:
            return "debug", "debug"

    def compress_adatrap_data(self, date):
        """
        Compress output adatrap data into a zip
        :param date: date (file name)
        """
        folder_path = os.path.join(self.data_path, date)
        self.send_log_message("Comprimiendo datos...")
        zip_filename = f"{date}.zip"
        with ZipFile(zip_filename, 'w') as zipObj:
            # Iterate over all the files in directory
            for folder_name, subfolders, filenames in os.walk(folder_path):
                # except kmls, reportes, debug
                exception_folders = ["kmls", "reportes", "debug"]
                if not os.path.split(folder_name)[1] in exception_folders:
                    for filename in filenames:
                        # create complete filepath of file in directory
                        file_path = os.path.join(folder_name, filename)
                        # Add file to zip
                        zipObj.write(file_path, basename(file_path))
        self.send_log_message("Compresión de datos exitosa.")

    def upload_output_data_to_s3(self, output_file_name):
        """
        Upload to S3 output adatrap data
        :param output_file_name: filename to upload
        """
        output_data_bucket = config('OUTPUT_DATA_BUCKET_NAME')
        self.send_log_message(f"Subiendo datos {output_file_name} ...")
        if not self.aws_session.check_bucket_exists(output_data_bucket):
            self.send_log_message(f"El bucket \'{output_data_bucket}\' no existe", error=True)
        try:
            self.aws_session.send_file_to_bucket(output_file_name, output_file_name, output_data_bucket)
            self.send_log_message("Datos subidos exitosamente.")
        except ClientError as e:
            self.send_log_message(e)
            self.send_log_message("Error al subir datos.", error=True)
