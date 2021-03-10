import aws


def main():
    session = aws.AWSSession()
    command = ["echo", "hello world"]
    session.submit_job("python-test", command)


if __name__ == "__main__":
    main()
