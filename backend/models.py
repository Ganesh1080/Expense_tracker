import pymysql
from config import Config
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal


class Database:
    def __init__(self):
        self.config = Config()

    def get_connection(self):
        return pymysql.connect(
            host=self.config.MYSQL_DATABASE_HOST,
            port=self.config.MYSQL_DATABASE_PORT,
            user=self.config.MYSQL_DATABASE_USER,
            password=self.config.MYSQL_DATABASE_PASSWORD,
            database=self.config.MYSQL_DATABASE_DB,
            charset=self.config.MYSQL_DATABASE_CHARSET,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def check_table_structure(self, table_name):
        """Check what columns exist in a table"""
        connection = None
        try:
            connection = self.get_connection()
            with connection.cursor() as cursor:
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                print(f"Table '{table_name}' structure:")
                for col in columns:
                    print(f"  - {col['Field']}: {col['Type']} ({col['Null']}, {col['Key']}, {col['Default']})")
                return columns
        except Exception as e:
            print(f"Error checking table structure: {e}")
            return []
        finally:
            if connection:
                connection.close()


def safe_float(value):
    """Convert decimal/numeric values to float safely"""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


class UserModel:
    def __init__(self, db_connection):
        self.db = db_connection

    def check_users_table(self):
        """Debug method to check users table structure"""
        return self.db.check_table_structure('users')

    def register_user(self, name, email, password):
        connection = None
        try:
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                # First check what columns exist
                cursor.execute("DESCRIBE users")
                columns = cursor.fetchall()
                available_columns = [col['Field'] for col in columns]
                print("DEBUG: Users table columns:", available_columns)
                
                # Check if user already exists
                cursor.execute("SELECT COUNT(*) as count FROM users WHERE email = %s", (email,))
                existing = cursor.fetchone()
                if existing['count'] > 0:
                    print(f"❌ User with email {email} already exists!")
                    raise Exception(f"User with email {email} already exists!")
                
                hashed_password = generate_password_hash(password)
                
                # FIX: Use 'username' instead of 'name' to match table structure
                if 'username' in available_columns:
                    sql = "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)"
                    cursor.execute(sql, (name, email, hashed_password))
                elif 'name' in available_columns:
                    sql = "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)"
                    cursor.execute(sql, (name, email, hashed_password))
                else:
                    # If no name/username column, just insert email and password
                    sql = "INSERT INTO users (email, password) VALUES (%s, %s)"
                    cursor.execute(sql, (email, hashed_password))
                
                connection.commit()
                print("✅ User registered successfully!")
                print(f"DEBUG: Registered user - Email: {email}")
                return cursor.lastrowid
        except Exception as e:
            print(f"❌ Error registering user: {e}")
            if connection:
                connection.rollback()
            raise e  # Re-raise to show error to user
        finally:
            if connection:
                connection.close()

    def get_user_by_email(self, email):
        connection = None
        try:
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                print(f"DEBUG: Searching for user with email: '{email}'")
                
                # First check table structure
                cursor.execute("DESCRIBE users")
                columns = cursor.fetchall()
                available_columns = [col['Field'] for col in columns]
                print(f"DEBUG: Available columns in users table: {available_columns}")
                
                # Now search for specific user
                sql = "SELECT * FROM users WHERE email = %s"
                cursor.execute(sql, (email,))
                user = cursor.fetchone()
                print(f"DEBUG: Query result for email '{email}': {user}")
                return user
        except Exception as e:
            print(f"❌ Error fetching user: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def validate_login(self, email, password):
        print(f"DEBUG: Attempting login for email: '{email}' with password: '{password}'")
        user = self.get_user_by_email(email)
        print("DEBUG: User from DB:", user)
        print("DEBUG: Entered Password:", password)
        
        if user:
            print(f"DEBUG: Found user. Stored password hash: {user['password']}")
            password_match = check_password_hash(user["password"], password)
            print(f"DEBUG: Password match result: {password_match}")
            if password_match:
                print("✅ Login successful!")
                return user
            else:
                print("❌ Password mismatch!")
        else:
            print("❌ User not found!")
        return None


# ===== FIXED EXPENSE MODEL WITH USER FILTERING =====
class ExpenseModel:
    def __init__(self, db_connection):
        self.db = db_connection
        self._date_column = None  # Cache the date column name
        self._table_columns = None  # Cache table structure
    
    def _get_current_user_id(self):
        """Get current user ID from session"""
        from flask import session
        return session.get('user_id', None)
    
    def _get_table_structure(self):
        """Get the actual table structure to work with existing columns"""
        if self._table_columns:
            return self._table_columns
            
        connection = None
        try:
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                cursor.execute("DESCRIBE expenses")
                columns = cursor.fetchall()
                available_columns = [col['Field'] for col in columns]
                
                print(f"DEBUG: Available columns in expenses table: {available_columns}")
                
                # Cache the structure
                self._table_columns = {
                    'all_columns': available_columns,
                    'has_title': 'title' in available_columns,
                    'has_name': 'name' in available_columns,
                    'has_description': 'description' in available_columns,
                    'has_user_id': 'user_id' in available_columns,
                    'date_column': self._detect_date_column(available_columns)
                }
                
                return self._table_columns
                
        except Exception as e:
            print(f"Error getting table structure: {e}")
            return {
                'all_columns': ['id', 'user_id', 'category_id', 'amount', 'description', 'date', 'created_at'],
                'has_title': False,
                'has_name': False,
                'has_description': True,
                'has_user_id': True,
                'date_column': 'date'
            }
        finally:
            if connection:
                connection.close()
    
    def _detect_date_column(self, available_columns):
        """Detect the date column name"""
        date_columns = ['expense_date', 'date', 'created_at', 'date_created', 'transaction_date']
        
        for col_name in date_columns:
            if col_name in available_columns:
                print(f"DEBUG: Using date column: {col_name}")
                return col_name
        
        # Fallback to first available column
        return available_columns[0] if available_columns else 'date'

    def add_expense(self, title, amount, category_id, description, expense_date):
        """Add expense using actual table structure"""
        connection = None
        try:
            structure = self._get_table_structure()
            date_column = structure['date_column']
            current_user_id = self._get_current_user_id()
            
            if not current_user_id:
                print("❌ No user logged in!")
                return None
            
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                # Build SQL based on available columns
                if structure['has_title'] and structure['has_description']:
                    # If both title and description columns exist
                    sql = f"""
                        INSERT INTO expenses (user_id, title, category_id, amount, description, {date_column})
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql, (current_user_id, title, category_id, float(amount), description, expense_date))
                elif structure['has_description']:
                    # Combine title and description if both provided
                    full_description = f"{title}: {description}" if description else title
                    
                    sql = f"""
                        INSERT INTO expenses (user_id, category_id, amount, description, {date_column})
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql, (current_user_id, category_id, float(amount), full_description, expense_date))
                else:
                    # Minimal insert if description column doesn't exist
                    sql = f"""
                        INSERT INTO expenses (user_id, category_id, amount, {date_column})
                        VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(sql, (current_user_id, category_id, float(amount), expense_date))
                
                connection.commit()
                print("✅ Expense added successfully!")
                return cursor.lastrowid
        except Exception as e:
            print(f"❌ Error adding expense: {e}")
            if connection:
                connection.rollback()
            return None
        finally:
            if connection:
                connection.close()

    def get_all_expenses(self, limit=None):
        """Get expenses for current user only"""
        connection = None
        try:
            structure = self._get_table_structure()
            date_column = structure['date_column']
            current_user_id = self._get_current_user_id()
            
            if not current_user_id:
                print("❌ No user logged in!")
                return []
            
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                # Build SELECT query based on available columns
                select_fields = ['e.id', 'e.amount', f'e.{date_column} as expense_date']
                
                if structure['has_title']:
                    select_fields.append('e.title')
                
                if structure['has_description']:
                    select_fields.append('e.description')
                
                # Add category info
                select_fields.extend(['c.name as category_name', 'c.id as category_id'])
                
                sql = f"""
                    SELECT {', '.join(select_fields)}
                    FROM expenses e
                    LEFT JOIN categories c ON e.category_id = c.id
                    WHERE e.user_id = %s
                    ORDER BY e.{date_column} DESC
                """
                
                if limit:
                    sql += f" LIMIT {limit}"

                cursor.execute(sql, (current_user_id,))
                expenses = cursor.fetchall()
                
                # Format the results and convert Decimal amounts to float
                for expense in expenses:
                    # ✅ FIX: Convert Decimal amounts to float
                    expense['amount'] = safe_float(expense['amount'])
                    
                    if expense["expense_date"]:
                        expense["expense_date"] = expense["expense_date"].strftime("%Y-%m-%d")
                    
                    # Handle title field
                    if structure['has_title']:
                        expense['title'] = expense.get('title', 'Expense')
                    else:
                        # If no title column, extract title from description or use category name
                        if 'description' in expense and expense['description']:
                            desc = expense['description']
                            if ':' in desc:
                                title_part, desc_part = desc.split(':', 1)
                                expense['title'] = title_part.strip()
                                expense['description'] = desc_part.strip()
                            else:
                                expense['title'] = desc[:30] + '...' if len(desc) > 30 else desc
                        else:
                            expense['title'] = expense.get('category_name', 'Expense')
                            expense['description'] = expense.get('description', '')
                
                return expenses
        except Exception as e:
            print(f"❌ Error getting expenses: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def get_expense_by_id(self, expense_id):
        """Get single expense by ID for current user only"""
        connection = None
        try:
            structure = self._get_table_structure()
            date_column = structure['date_column']
            current_user_id = self._get_current_user_id()
            
            if not current_user_id:
                print("❌ No user logged in!")
                return None
            
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                select_fields = ['e.id', 'e.amount', 'e.category_id', f'e.{date_column} as expense_date']
                
                if structure['has_title']:
                    select_fields.append('e.title')
                
                if structure['has_description']:
                    select_fields.append('e.description')
                
                select_fields.append('c.name as category_name')
                
                sql = f"""
                    SELECT {', '.join(select_fields)}
                    FROM expenses e
                    LEFT JOIN categories c ON e.category_id = c.id
                    WHERE e.id = %s AND e.user_id = %s
                """
                cursor.execute(sql, (expense_id, current_user_id))
                expense = cursor.fetchone()
                
                if expense:
                    # ✅ FIX: Convert Decimal amount to float
                    expense['amount'] = safe_float(expense['amount'])
                    
                    if expense["expense_date"]:
                        expense["expense_date"] = expense["expense_date"].strftime("%Y-%m-%d")
                    
                    # Handle title field
                    if structure['has_title']:
                        expense['title'] = expense.get('title', 'Expense')
                    else:
                        # Extract title from description if needed
                        if 'description' in expense and expense['description']:
                            desc = expense['description']
                            if ':' in desc:
                                title_part, desc_part = desc.split(':', 1)
                                expense['title'] = title_part.strip()
                                expense['description'] = desc_part.strip()
                            else:
                                expense['title'] = desc
                        else:
                            expense['title'] = expense.get('category_name', 'Expense')
                            expense['description'] = expense.get('description', '')
                
                return expense
        except Exception as e:
            print(f"❌ Error getting expense: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def update_expense(self, expense_id, title, amount, category_id, description, expense_date):
        """Update expense for current user only"""
        connection = None
        try:
            structure = self._get_table_structure()
            date_column = structure['date_column']
            current_user_id = self._get_current_user_id()
            
            if not current_user_id:
                print("❌ No user logged in!")
                return False
            
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                # Build update based on available columns
                if structure['has_title'] and structure['has_description']:
                    sql = f"""
                        UPDATE expenses 
                        SET title=%s, amount=%s, category_id=%s, description=%s, {date_column}=%s
                        WHERE id=%s AND user_id=%s
                    """
                    cursor.execute(sql, (title, float(amount), category_id, description, expense_date, expense_id, current_user_id))
                elif structure['has_description']:
                    full_description = f"{title}: {description}" if description else title
                    sql = f"""
                        UPDATE expenses 
                        SET amount=%s, category_id=%s, description=%s, {date_column}=%s
                        WHERE id=%s AND user_id=%s
                    """
                    cursor.execute(sql, (float(amount), category_id, full_description, expense_date, expense_id, current_user_id))
                else:
                    sql = f"""
                        UPDATE expenses 
                        SET amount=%s, category_id=%s, {date_column}=%s
                        WHERE id=%s AND user_id=%s
                    """
                    cursor.execute(sql, (float(amount), category_id, expense_date, expense_id, current_user_id))
                
                connection.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error updating expense: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def delete_expense(self, expense_id):
        """Delete expense for current user only"""
        connection = None
        try:
            current_user_id = self._get_current_user_id()
            
            if not current_user_id:
                print("❌ No user logged in!")
                return False
            
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s", (expense_id, current_user_id))
                connection.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error deleting expense: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def get_expenses_by_date_range(self, start_date, end_date):
        """Get expenses within date range for current user only"""
        connection = None
        try:
            structure = self._get_table_structure()
            date_column = structure['date_column']
            current_user_id = self._get_current_user_id()
            
            if not current_user_id:
                print("❌ No user logged in!")
                return []
            
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                select_fields = ['e.id', 'e.amount', f'e.{date_column} as expense_date']
                
                if structure['has_title']:
                    select_fields.append('e.title')
                
                if structure['has_description']:
                    select_fields.append('e.description')
                
                select_fields.extend(['c.name as category_name', 'c.id as category_id'])
                
                sql = f"""
                    SELECT {', '.join(select_fields)}
                    FROM expenses e
                    LEFT JOIN categories c ON e.category_id = c.id
                    WHERE e.{date_column} BETWEEN %s AND %s AND e.user_id = %s
                    ORDER BY e.{date_column} DESC
                """
                cursor.execute(sql, (start_date, end_date, current_user_id))
                expenses = cursor.fetchall()
                
                # Format results and convert Decimal amounts
                for expense in expenses:
                    # ✅ FIX: Convert Decimal amount to float
                    expense['amount'] = safe_float(expense['amount'])
                    
                    if expense["expense_date"]:
                        expense["expense_date"] = expense["expense_date"].strftime("%Y-%m-%d")
                    
                    # Handle title field
                    if structure['has_title']:
                        expense['title'] = expense.get('title', 'Expense')
                    else:
                        # Extract title from description
                        if 'description' in expense and expense['description']:
                            desc = expense['description']
                            if ':' in desc:
                                title_part, desc_part = desc.split(':', 1)
                                expense['title'] = title_part.strip()
                                expense['description'] = desc_part.strip()
                            else:
                                expense['title'] = desc[:30] + '...' if len(desc) > 30 else desc
                        else:
                            expense['title'] = expense.get('category_name', 'Expense')
                            expense['description'] = expense.get('description', '')
                
                return expenses
        except Exception as e:
            print(f"❌ Error getting expenses by date range: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def get_total_expense(self, start_date=None, end_date=None):
        """Get total expenses for current user only"""
        connection = None
        try:
            structure = self._get_table_structure()
            date_column = structure['date_column']
            current_user_id = self._get_current_user_id()
            
            if not current_user_id:
                print("❌ No user logged in!")
                return 0.0
            
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                if start_date and end_date:
                    sql = f"SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE {date_column} BETWEEN %s AND %s AND user_id = %s"
                    cursor.execute(sql, (start_date, end_date, current_user_id))
                else:
                    sql = "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = %s"
                    cursor.execute(sql, (current_user_id,))
                    
                result = cursor.fetchone()
                # ✅ FIX: Convert Decimal total to float
                total = safe_float(result["total"]) if result and result["total"] else 0.0
                return total
        except Exception as e:
            print(f"❌ Error getting total expense: {e}")
            return 0.0
        finally:
            if connection:
                connection.close()

    def get_expenses_by_category(self):
        """Get expenses by category for current user only"""
        connection = None
        try:
            current_user_id = self._get_current_user_id()
            
            if not current_user_id:
                print("❌ No user logged in!")
                return []
            
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                sql = """
                    SELECT c.name as category_name, 
                           COALESCE(SUM(e.amount), 0) as total_amount, 
                           COUNT(e.id) as count
                    FROM categories c
                    LEFT JOIN expenses e ON e.category_id = c.id AND e.user_id = %s
                    GROUP BY c.id, c.name
                    HAVING total_amount > 0
                    ORDER BY total_amount DESC
                """
                cursor.execute(sql, (current_user_id,))
                category_expenses = cursor.fetchall()
                
                # ✅ FIX: Convert Decimal amounts to float
                for category in category_expenses:
                    category['total_amount'] = safe_float(category['total_amount'])
                
                return category_expenses
        except Exception as e:
            print(f"❌ Error getting expenses by category: {e}")
            return []
        finally:
            if connection:
                connection.close()


class CategoryModel:
    def __init__(self, db_connection):
        self.db = db_connection

    def get_all_categories(self):
        connection = None
        try:
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM categories ORDER BY name")
                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting categories: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def add_category(self, name, description):
        connection = None
        try:
            connection = self.db.get_connection()
            with connection.cursor() as cursor:
                sql = "INSERT INTO categories (name, description) VALUES (%s, %s)"
                cursor.execute(sql, (name, description))
                connection.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error adding category: {e}")
            return None
        finally:
            if connection:
                connection.close()