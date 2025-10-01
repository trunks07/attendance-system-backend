import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from app.config.credentials import Database

MONGO_URI = Database.url
DB_NAME = Database.name
# Global connection cache
client = None
db_instance = None


async def connect_to_mongo():
    """Connect to MongoDB with transaction support"""
    global client, db_instance
    if client is not None:
        return True

    try:
        print(f"🔁 Connecting to MongoDB at {MONGO_URI}")
        # Add transaction-specific parameters
        client = AsyncIOMotorClient(
            MONGO_URI,
            maxPoolSize=10,  # Increased for transactions
            minPoolSize=2,
            connectTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,  # Essential for transactions
            w="majority",  # Write concern for ACID
        )
        db_instance = client[DB_NAME]

        # Verify connection and transaction support
        await db_instance.command({"ping": 1})

        # Check if connected to replica set
        ismaster = await db_instance.command("ismaster")
        if not ismaster.get("setName"):
            logging.warning("⚠️ Not connected to a replica set. Transactions disabled.")

        print("✅ MongoDB connection established with transaction support")
        return True
    except ConnectionFailure as e:
        logging.error(f"❌ MongoDB connection failed: {str(e)}")
        client = None
        db_instance = None
        return False
    except Exception as e:
        logging.exception(f"❌ Unexpected error: {str(e)}")
        client = None
        db_instance = None
        return False


async def close_mongo_connection():
    """Close MongoDB connection (only for local development)"""
    global client, db_instance
    if client:
        client.close()
        client = None
        db_instance = None
        print("🔌 MongoDB connection closed")


async def get_db():
    """Get database instance with connection verification"""
    # global db_instance
    if db_instance is None:
        if not await connect_to_mongo():
            raise RuntimeError("Database connection not available")

    try:
        # Verify connection is still alive
        await db_instance.command("ping")
        return db_instance
    except ConnectionFailure:
        print("MongoDB connection lost, attempting to reconnect...")
        if await connect_to_mongo():
            return db_instance
        raise RuntimeError("Failed to reconnect to MongoDB")
