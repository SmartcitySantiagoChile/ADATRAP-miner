import argparse
import logging
import sys

from decouple import config

logger = logging.getLogger(__name__)


def main(argv):
    """
    Script to execute ADATRAP
    """

    logging.basicConfig(level=logging.INFO)

    # Arguments and description
    parser = argparse.ArgumentParser(description="Script to execute ADATRAP")
    parser.add_argument("date", help="date to execute adatrap", nargs="+")

    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    args = parser.parse_args(argv[1:])
    date = args.date
    path = config("ADATRAP_PATH")
    logger.info(f"{date} {path}")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
