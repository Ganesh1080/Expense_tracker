import os

class Config:
    # MySQL Database Configuration
    MYSQL_DATABASE_HOST = 'localhost'
    MYSQL_DATABASE_PORT = 3306
    MYSQL_DATABASE_USER = 'root'  # Change this to your MySQL username
    MYSQL_DATABASE_PASSWORD = 'Career@1080'  # Change this to your MySQL password
    MYSQL_DATABASE_DB = 'expense_tracker'
    MYSQL_DATABASE_CHARSET = 'utf8mb4'
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    DEBUG = True