import argparse
import logging
import sys

import botocore.exceptions
from decouple import config

import adatrapMiner.aws as aws

logger = logging.getLogger(__name__)
general_log_stream = config("GENERAL_LOG_STREAM")


def main(argv):
    """
    Script to manage EC2 instances
    """
    logging.basicConfig(level=logging.INFO)

    # Arguments and description
    parser = argparse.ArgumentParser(description="manage EC2 instances and ADATRAP")
    parser.add_argument(
        "-c",
        "--create_key_par",
        help="Create EC2 pair for .env given user",
        action="store_true",
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )

    args = parser.parse_args(argv[1:])

    # Create Key Par
    session = aws.AWSSession()
    if args.create_key_par:
        try:
            session.create_key_pair()
            message = "¡Keypair creado exitosamente! El archivo ec2-keypair.pem se encuentra en la raíz del proyecto."
            logger.info(message)
            session.send_log_event(general_log_stream, message)
        except botocore.exceptions.ClientError:
            message = "El keypair 'ec2-keypair' ya existe."
            logger.error(message)
            session.send_log_event(general_log_stream, message)
    else:
        # Create EC2 instance
        status = session.run_ec2_instance()
        instance_id = status["Instances"][0]["InstanceId"]
        message = f"Instancia creada con id: {instance_id}"
        logger.info(message)
        session.send_log_event(general_log_stream, message)

        # Create EC2 Log Stream
        session.create_log_stream(instance_id)
        message = f"Log Stream creado con nombre: {instance_id}"
        logger.info(message)
        session.send_log_event(general_log_stream, message)

        # Send initial message to EC2 Log Stream
        message = "Instancia creada correctamente."
        session.send_log_event(instance_id, message)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
