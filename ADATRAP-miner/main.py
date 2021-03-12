import aws


def main():
    session = aws.AWSSession()
    status = session.create_ec2_instance()
    print(status)


if __name__ == "__main__":
    main()
