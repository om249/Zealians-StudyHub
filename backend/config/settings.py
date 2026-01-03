# Configuration module
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/zealians_db')
    DEBUG = os.getenv('FLASK_ENV') == 'development'
