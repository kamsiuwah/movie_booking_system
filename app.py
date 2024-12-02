from flask import Flask, render_template, request, redirect, session
import csv

app = Flask(__name__)
app.secret_key = 'your-secret-key'

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/movies')
def movies():
    movies_list = []
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            movies_list.append(row)
    return render_template('movies.html', movies=movies_list)

# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Save user to CSV
        with open('data/users.csv', 'a') as file:
            writer = csv.writer(file)
            writer.writerow([name, email, password])

        return redirect('/login')
    return render_template('register.html')

# Login Route
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

@app.route('/logout')
def logout():
    session.pop('user', None)  # Clear session
    return redirect('/')



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

