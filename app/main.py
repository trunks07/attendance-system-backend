
import os
import asyncio
import uvicorn

from mangum import Mangum
from fastapi import FastAPI
from app.web import routing
from app.cors import cors_settings
from contextlib import asynccontextmanager
from app.config.database import close_mongo_connection, connect_to_mongo

# Check if running in Lambda
IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management - optimized for Lambda"""
    try:
        # Connect to MongoDB only if not in Lambda
        if not IS_LAMBDA and not await connect_to_mongo():
            print("❌ Failed to connect to MongoDB on startup")
        yield
    finally:
        # Close connection only in local development
        if not IS_LAMBDA:
            await close_mongo_connection()

async def schedule_mass_sync():
    try:
        await asyncio.gather(
            # add function for CRON here
        )
    except Exception as e:
        print(f"An error occurred during sync: {e}")


def lambda_handler(event, context):
    if "source" in event and event["source"] == "aws.scheduler":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(schedule_mass_sync())
        return {"statusCode": 200, "body": "Sync job completed successfully."}
    else:
        return asgi_handler(event, context)

app = routing(FastAPI(lifespan=lifespan))
app = cors_settings(app)
asgi_handler = Mangum(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)