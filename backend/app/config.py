import os
from dotenv import load_dotenv

# Load env variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smart_inventory.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
