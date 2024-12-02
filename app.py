from flask import Flask, render_template, request, redirect, session
import csv
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Required for session management

# -------------------- Routes --------------------

# Home Page
@app.route('/')
def home():
    return render_template('index.html')

# User Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check if email already exists
        with open('data/users.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['email'] == email:
                    return "Email already registered!"

        # Save user to CSV
        with open('data/users.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([name, email, password])

        return redirect('/login')

    return render_template('register.html')

# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Validate user
        with open('data/users.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['email'] == email and row['password'] == password:
                    session['user'] = row['name']  # Store user session
                    return redirect('/movies')

        return "Invalid credentials!"

    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('user', None)  # Clear session
    return redirect('/')

# Browse Movies
@app.route('/movies')
def movies():
    movies_list = []
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            movies_list.append(row)
    return render_template('movies.html', movies=movies_list)

# Purchase Tickets
@app.route('/book/<movie_id>', methods=['POST'])
def book_ticket(movie_id):
    if 'user' not in session:
        return redirect('/login')

    user_email = session.get('user')
    ticket_id = f"{movie_id}-{user_email}"  # Unique ticket ID
    with open('data/tickets.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([ticket_id, movie_id, user_email])

    return redirect('/history')

# View Purchase History
@app.route('/history')
def view_history():
    if 'user' not in session:
        return redirect('/login')

    user_email = session.get('user')
    tickets = []
    with open('data/tickets.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['user_email'] == user_email:
                tickets.append(row)
    return render_template('history.html', tickets=tickets)

# Admin Dashboard
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user' not in session or session.get('user') != 'admin':
        return redirect('/login')

    movies_list = []
    if request.method == 'POST':
        title = request.form['title']
        genre = request.form['genre']
        description = request.form['description']

        with open('data/movies.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([title, genre, description])

    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            movies_list.append(row)

    return render_template('admin_dashboard.html', movies=movies_list)

# -------------------- Helper Functions --------------------
# Ensure data directory exists
def ensure_data_files():
    os.makedirs('data', exist_ok=True)

    # Users CSV
    if not os.path.exists('data/users.csv'):
        with open('data/users.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['name', 'email', 'password'])

    # Movies CSV
    if not os.path.exists('data/movies.csv'):
        with open('data/movies.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'title', 'genre', 'description'])

    # Tickets CSV
    if not os.path.exists('data/tickets.csv'):
        with open('data/tickets.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['ticket_id', 'movie_id', 'user_email'])

# Initialize data files
ensure_data_files()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
