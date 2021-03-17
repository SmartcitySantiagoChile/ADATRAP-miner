import argparse
import logging
import sys

import botocore.exceptions

import adatrapMiner.aws as aws

logger = logging.getLogger(__name__)


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

    if args.create_key_par:
        session = aws.AWSSession()
        try:
            session.create_key_pair()
            logger.info(
                "¡Keypair creado exitosamente! El archivo ec2-keypair.pem se encuentra en la raíz del proyecto."
            )
        except botocore.exceptions.ClientError:
            logger.error("El keypair 'ec2-keypair' ya existe.")
    session = aws.AWSSession()
    # status = session.create_ec2_instance()
    status = session.run_ec2_instance()
    instance_id = status["Instances"][0]["InstanceId"]
    logger.info(f"Instancia creada con id: {instance_id}")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
