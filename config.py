import os
from dotenv import load_dotenv

load_dotenv()

MILESTONE_SERVER_URL = os.getenv("MILESTONE_SERVER_URL", "").rstrip("/")
MILESTONE_USERNAME = os.getenv("MILESTONE_USERNAME", "")
MILESTONE_PASSWORD = os.getenv("MILESTONE_PASSWORD", "")
