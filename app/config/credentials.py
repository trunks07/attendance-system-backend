import os
from dotenv import load_dotenv

if os.getenv("AWS_EXECUTION_ENV") is None:
    load_dotenv()

class Database:
    url = os.getenv("MONGODB_URL")
    name = os.getenv("DB_NAME")

class Hash:
    key = os.getenv("APP_KEY")
    algorithm = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))