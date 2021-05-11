import argparse
import logging
import sys

from decouple import config

import aws
import windows_manager

logger = logging.getLogger(__name__)
data_path: str = "ADATRAP"
general_log_stream: str = config("GENERAL_LOG_STREAM")
executable_adatrap: str = 'pvmtsc_v0.2.exe'
config_file_adatrap: str = 'pvmtsc_v0.2.par'
config_file_replacements: dict = {
    '{po_path}': 'op_path_replacement',
    '{service_detail_file}': 'service_detail',
    '{date}': 'date',
    '{po_date}': 'podate'
}

data_buckets = [config('GPS_BUCKET_NAME'), config('FILE_196_BUCKET_NAME'), config('TRANSACTION_BUCKET_NAME'),
                config('OP_PROGRAM_BUCKET_NAME'), config("SERVICE_DETAIL_BUCKET_NAME")]
bucket_names = ["gps", "196", "transaction", "op", "service_detail"]


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
    command_manager = windows_manager.WindowsManager(logger, session, general_log_stream, config_file_replacements,
                                                     config_file_adatrap, data_path, data_buckets, bucket_names,
                                                     executable_adatrap,
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
    stdout, stderr = command_manager.run_adatrap(date)
    if stdout:
        # Compress output data
        command_manager.compress_adatrap_data(date)
        output_file_name = f"{date}.zip"

        # Upload to S3
        command_manager.upload_output_data_to_s3(output_file_name)

    if stderr:
        command_manager.send_log_message(stdout)
        command_manager.send_log_message(f"Proceso ADATRAP para la instancia {command_manager.instance_id} finalizado.",
                                         general=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
