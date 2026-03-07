import os
from dotenv import load_dotenv

# MUST happen before importing the app
load_dotenv()

import uvicorn
from app.main import app

if __name__ == "__main__":
    print("🚀 Starting Refactored QnAI Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
