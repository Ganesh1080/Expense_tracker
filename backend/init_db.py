import pymysql
from config import Config

def create_database():
    """Create the expense_tracker database if it doesn't exist"""
    try:
        # Connect to MySQL server (without specifying database)
        connection = pymysql.connect(
            host=Config.MYSQL_DATABASE_HOST,
            port=Config.MYSQL_DATABASE_PORT,
            user=Config.MYSQL_DATABASE_USER,
            password=Config.MYSQL_DATABASE_PASSWORD,
            charset=Config.MYSQL_DATABASE_CHARSET
        )
        
        with connection.cursor() as cursor:
            # Create database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DATABASE_DB}")
            print(f"Database '{Config.MYSQL_DATABASE_DB}' created successfully!")
            
    except Exception as e:
        print(f"Error creating database: {e}")
    finally:
        connection.close()

def create_tables():
    """Create the necessary tables"""
    try:
        # Connect to the expense_tracker database
        connection = pymysql.connect(
            host=Config.MYSQL_DATABASE_HOST,
            port=Config.MYSQL_DATABASE_PORT,
            user=Config.MYSQL_DATABASE_USER,
            password=Config.MYSQL_DATABASE_PASSWORD,
            database=Config.MYSQL_DATABASE_DB,
            charset=Config.MYSQL_DATABASE_CHARSET
        )
        
        with connection.cursor() as cursor:
            # Create categories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create expenses table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    category_id INT,
                    description TEXT,
                    expense_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
            """)
            
            # Insert default categories
            default_categories = [
                ('Food & Dining', 'Restaurants, groceries, and food-related expenses'),
                ('Transportation', 'Gas, public transport, car maintenance'),
                ('Utilities', 'Electricity, water, internet, phone bills'),
                ('Entertainment', 'Movies, games, hobbies, and leisure activities'),
                ('Healthcare', 'Medical bills, medicines, doctor visits'),
                ('Shopping', 'Clothes, electronics, and other purchases'),
                ('Education', 'Books, courses, and learning materials'),
                ('Other', 'Miscellaneous expenses')
            ]
            
            for category_name, category_desc in default_categories:
                cursor.execute("""
                    INSERT IGNORE INTO categories (name, description) 
                    VALUES (%s, %s)
                """, (category_name, category_desc))
            
            connection.commit()
            print("Tables created successfully!")
            print("Default categories added!")
            
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    create_database()
    create_tables()