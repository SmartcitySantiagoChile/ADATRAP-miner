import argparse
import logging
import os
import subprocess
import sys

from decouple import config

from adatrapMiner import aws

logger = logging.getLogger(__name__)
general_log_stream = config("GENERAL_LOG_STREAM")


def main(argv):
    """
    Script to execute ADATRAP
    """

    logging.basicConfig(level=logging.INFO)

    # Arguments and description
    parser = argparse.ArgumentParser(description="Script to execute ADATRAP")
    parser.add_argument("date", help="Date to execute adatrap")
    parser.add_argument("id", help="EC2 Instance ID")
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    args = parser.parse_args(argv[1:])
    date = args.date
    instance_id = args.id
    path = config("ADATRAP_PATH")

    # Initial Log
    session = aws.AWSSession()

    message = "Instancia inicializada."
    logger.info(message)
    session.send_log_event(instance_id, message)

    # Run ADATRAP
    subprocess.run(
        [os.path.join(path, "pvmts_dummy.exe"), os.path.join(path, f"{date}.par")],
        shell=True,
        check=True,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv))
