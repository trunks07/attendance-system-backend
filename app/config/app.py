import os
from dotenv import load_dotenv

if os.getenv("AWS_EXECUTION_ENV") is None:
    load_dotenv()


class Test:
    endpoint = os.getenv("TEST_ENDPOINT")
