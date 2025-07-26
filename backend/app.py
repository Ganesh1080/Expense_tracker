from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_cors import CORS
from models import ExpenseModel, CategoryModel, UserModel, Database
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import calendar
from functools import wraps

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
CORS(app)

# ✅ Create Database instance (not connection)
db_instance = Database()

# ✅ Initialize models with Database instance
expense_model = ExpenseModel(db_instance)
category_model = CategoryModel(db_instance)
user_model = UserModel(db_instance)

# ✅ ADD CUSTOM JINJA2 FILTER FOR COLOR PICKER
@app.template_filter('color_picker')
def color_picker_filter(index):
    """Generate colors for chart categories based on index"""
    colors = [
        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
        '#9966FF', '#FF9F40', '#C9CBCF', '#FF6B6B',
        '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57'
    ]
    return colors[(index - 1) % len(colors)]

# ✅ LOGIN REQUIRED DECORATOR
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ✅ HELPER FUNCTION TO GET CURRENT USER INFO
def get_current_user():
    """Get current user information from session"""
    if 'user_id' in session:
        return {
            'user_id': session['user_id'],
            'user_name': session.get('user_name', 'User'),
            'user_email': session.get('user_email', '')
        }
    return None

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Redirect if already logged in
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name') or request.form.get('username', '')
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            
            # Validate input
            if not all([name, email, password]):
                flash('All fields are required!', 'danger')
                return render_template('register.html')
            
            # Validate password length
            if len(password) < 6:
                flash('Password must be at least 6 characters long!', 'danger')
                return render_template('register.html')
            
            # Try to register user
            user_id = user_model.register_user(name, email, password)
            if user_id:
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Registration failed!', 'danger')
                
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect if already logged in
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Email and password are required!', 'danger')
            return render_template('login.html')
            
        print(f"🔐 Login attempt for: {email}")
        user = user_model.validate_login(email, password)
        
        if user:
            # ✅ CLEAR ANY EXISTING SESSION DATA
            session.clear()
            
            # ✅ SET NEW SESSION DATA
            session['user_id'] = user['id']
            session['user_name'] = user.get('username') or user.get('name') or user['email']
            session['user_email'] = user['email']
            
            # Make session permanent (optional)
            session.permanent = True
            
            print(f"✅ Login successful for user ID: {user['id']}")
            flash(f'Welcome back, {session["user_name"]}!', 'success')
            return redirect(url_for('index'))
        else:
            print(f"❌ Login failed for: {email}")
            flash('Invalid email or password!', 'danger')
            
    return render_template('login.html')

# @app.route('/logout')
# def logout():
#     user_name = session.get('user_name', 'User')
#     # ✅ COMPLETELY CLEAR THE SESSION
#     session.clear()
#     flash(f'Goodbye {user_name}! You have been logged out.', 'info')
#     return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    try:
        # ✅ GET CURRENT USER INFO
        current_user = get_current_user()
        print(f"📊 Loading dashboard for user ID: {current_user['user_id']}")
        
        # ✅ GET USER-SPECIFIC DATA
        recent_expenses = expense_model.get_all_expenses(limit=10)
        total_expense = expense_model.get_total_expense()

        today = date.today()
        first_day = today.replace(day=1)
        last_day = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        monthly_expense = expense_model.get_total_expense(first_day, last_day)

        category_expenses = expense_model.get_expenses_by_category()

        print(f"📈 Dashboard stats - Total: ${total_expense}, Monthly: ${monthly_expense}, Recent expenses: {len(recent_expenses)}")

        return render_template('index.html', 
                               recent_expenses=recent_expenses,
                               total_expense=total_expense,
                               monthly_expense=monthly_expense,
                               category_expenses=category_expenses,
                               current_user=current_user)
    except Exception as e:
        print(f"❌ Error loading dashboard: {e}")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('index.html', 
                               recent_expenses=[],
                               total_expense=0,
                               monthly_expense=0,
                               category_expenses=[],
                               current_user=get_current_user())

@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    current_user = get_current_user()
    
    if request.method == 'POST':
        try:
            title = request.form.get('title', '')
            amount = request.form.get('amount', '')
            category_id = request.form.get('category_id', '')
            expense_date = request.form.get('expense_date', '')
            description = request.form.get('description', '')

            # Validate required fields
            if not all([title, amount, category_id, expense_date]):
                flash('Title, amount, category, and date are required!', 'danger')
                categories = category_model.get_all_categories()
                return render_template('add_expense.html', 
                                     categories=categories, 
                                     edit_mode=False,
                                     current_user=current_user)

            print(f"➕ Adding expense for user ID: {current_user['user_id']}")
            
            # Add the expense with corrected parameter order
            result = expense_model.add_expense(
                title=title,
                amount=float(amount),
                category_id=int(category_id),
                description=description,
                expense_date=expense_date
            )

            if result:
                flash('Expense added successfully!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Error adding expense. Please try again.', 'danger')
                
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
            print(f"❌ Error in add_expense route: {e}")

    categories = category_model.get_all_categories()
    return render_template('add_expense.html', 
                         categories=categories, 
                         edit_mode=False,
                         current_user=current_user)

@app.route('/edit_expense/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    current_user = get_current_user()
    
    if request.method == 'POST':
        try:
            title = request.form.get('title', '')
            amount = request.form.get('amount', '')
            category_id = request.form.get('category_id', '')
            expense_date = request.form.get('expense_date', '')
            description = request.form.get('description', '')

            # Validate required fields
            if not all([title, amount, category_id, expense_date]):
                flash('Title, amount, category, and date are required!', 'danger')
                expense = expense_model.get_expense_by_id(expense_id)
                categories = category_model.get_all_categories()
                return render_template('add_expense.html', 
                                     categories=categories, 
                                     expense=expense, 
                                     edit_mode=True,
                                     current_user=current_user)

            print(f"✏️ Editing expense {expense_id} for user ID: {current_user['user_id']}")
            
            # Update the expense
            result = expense_model.update_expense(
                expense_id=expense_id,
                title=title,
                amount=float(amount),
                category_id=int(category_id),
                description=description,
                expense_date=expense_date
            )

            if result:
                flash('Expense updated successfully!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Error updating expense. Expense not found or access denied.', 'danger')
                
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
            print(f"❌ Error in edit_expense route: {e}")

    # GET request - load expense for editing
    try:
        expense = expense_model.get_expense_by_id(expense_id)
        if not expense:
            flash('Expense not found or access denied!', 'danger')
            return redirect(url_for('index'))
        
        categories = category_model.get_all_categories()
        return render_template('add_expense.html', 
                             categories=categories, 
                             expense=expense, 
                             edit_mode=True,
                             current_user=current_user)
    except Exception as e:
        flash(f'Error loading expense: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/delete_expense/<int:expense_id>')
@login_required
def delete_expense(expense_id):
    try:
        current_user = get_current_user()
        print(f"🗑️ Deleting expense {expense_id} for user ID: {current_user['user_id']}")
        
        success = expense_model.delete_expense(expense_id)
        if success:
            flash('Expense deleted successfully!', 'success')
        else:
            flash('Error deleting expense or expense not found!', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('index'))

@app.route('/reports')
@login_required
def reports():
    try:
        current_user = get_current_user()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not start_date or not end_date:
            today = date.today()
            start_date = today.replace(day=1).strftime('%Y-%m-%d')
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_date = today.replace(day=last_day).strftime('%Y-%m-%d')

        print(f"📊 Loading reports for user ID: {current_user['user_id']}")
        
        expenses = expense_model.get_expenses_by_date_range(start_date, end_date)
        total_amount = expense_model.get_total_expense(start_date, end_date)
        category_expenses = expense_model.get_expenses_by_category()

        return render_template('reports.html',
                               expenses=expenses,
                               total_amount=total_amount,
                               category_expenses=category_expenses,
                               start_date=start_date,
                               end_date=end_date,
                               current_user=current_user)
    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'error')
        return render_template('reports.html',
                               expenses=[],
                               total_amount=0,
                               category_expenses=[],
                               start_date='',
                               end_date='',
                               current_user=get_current_user())

# ✅ API ROUTES WITH USER FILTERING
@app.route('/api/expenses')
@login_required
def api_expenses():
    try:
        current_user = get_current_user()
        expenses = expense_model.get_all_expenses()
        return jsonify({
            'success': True,
            'user_id': current_user['user_id'],
            'expenses': expenses
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories')
def api_categories():
    return jsonify(category_model.get_all_categories())

@app.route('/api/expenses/category/<int:category_id>')
@login_required
def api_expenses_by_category(category_id):
    return jsonify([])  # Optional to implement

@app.route('/api/stats')
@login_required
def api_stats():
    try:
        current_user = get_current_user()
        today = date.today()
        first_day = today.replace(day=1)
        last_day = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])

        stats = {
            'user_id': current_user['user_id'],
            'total_expense': expense_model.get_total_expense(),
            'monthly_expense': expense_model.get_total_expense(first_day, last_day),
            'category_expenses': expense_model.get_expenses_by_category()
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ✅ DEBUG ROUTES
@app.route('/debug/session_info')
def debug_session_info():
    """Debug route to check current session"""
    return jsonify({
        'session_data': dict(session),
        'current_user': get_current_user(),
        'is_logged_in': 'user_id' in session
    })

@app.route('/debug/expenses_table')
@login_required
def debug_expenses_table():
    """Debug route to see expenses table structure and data"""
    try:
        current_user = get_current_user()
        connection = db_instance.get_connection()
        with connection.cursor() as cursor:
            # Check table structure
            cursor.execute("DESCRIBE expenses")
            columns = cursor.fetchall()
            
            # Check user-specific data
            cursor.execute("SELECT * FROM expenses WHERE user_id = %s LIMIT 5", (current_user['user_id'],))
            user_data = cursor.fetchall()
            
            # Count user's total records
            cursor.execute("SELECT COUNT(*) as count FROM expenses WHERE user_id = %s", (current_user['user_id'],))
            user_count = cursor.fetchone()
            
            # Count all records
            cursor.execute("SELECT COUNT(*) as count FROM expenses")
            total_count = cursor.fetchone()
            
        connection.close()
        
        return jsonify({
            'current_user': current_user,
            'table_structure': columns,
            'user_sample_data': user_data,
            'user_records': user_count['count'],
            'total_records': total_count['count'],
            'available_columns': [col['Field'] for col in columns]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/all_tables')
def debug_all_tables():
    """Debug route to see all table structures"""
    try:
        connection = db_instance.get_connection()
        results = {}
        
        # Get all tables
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = list(table.values())[0]  # Get table name
                cursor.execute(f"DESCRIBE {table_name}")
                results[table_name] = {
                    'structure': cursor.fetchall(),
                    'columns': []
                }
                # Get just column names for easier reading
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                results[table_name]['columns'] = [col['Field'] for col in columns]
        
        connection.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/create_test_user')
def create_test_user():
    """Debug route to create a test user"""
    try:
        import random
        test_num = random.randint(100, 999)
        email = f'test{test_num}@example.com'
        
        user_id = user_model.register_user(f'Test User {test_num}', email, 'password123')
        if user_id:
            return jsonify({
                'success': True,
                'message': f'Test user created with ID: {user_id}',
                'email': email,
                'password': 'password123'
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to create user'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if request.method == 'GET':
        # Show logout confirmation page
        current_user = get_current_user()
        if not current_user:
            # If not logged in, redirect to login
            return redirect(url_for('login'))
        return render_template('logout.html', current_user=current_user)
    
    elif request.method == 'POST':
        # Actually perform logout
        user_name = session.get('user_name', 'User')
        # ✅ COMPLETELY CLEAR THE SESSION
        session.clear()
        flash(f'Goodbye {user_name}! You have been logged out successfully.', 'success')
        return redirect(url_for('login'))


# ✅ CONTEXT PROCESSOR TO MAKE CURRENT USER AVAILABLE IN ALL TEMPLATES
@app.context_processor
def inject_current_user():
    return {'current_user': get_current_user()}

# ✅ BEFORE REQUEST HANDLER TO LOG SESSION INFO
@app.before_request
def before_request():
    if request.endpoint and not request.endpoint.startswith('static'):
        print(f"🌐 {request.method} {request.endpoint} - User: {session.get('user_id', 'Anonymous')}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)