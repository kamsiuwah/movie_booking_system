from flask import Flask, render_template, request, redirect, session, url_for
import csv
import os
import bcrypt
import stripe
import json
from datetime import timedelta
import barcode
from barcode.writer import ImageWriter
from flask_mail import Mail, Message
from datetime import datetime


app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Required for session management
stripe.api_key = 'sk_test_51QRlQkCV3XkBzb7OlrDP3tHy8TrtvEwvjcbT3rMsxApUuLceTPNs5dRAHkJpg0J6zWDVtDOHCsWvPKLmu0o3dRn600OmSzOZTA'
app.permanent_session_lifetime = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'uwahkamsi12@gmail.com'  
app.config['MAIL_PASSWORD'] = 'kobg dafz cksl higy'  

mail = Mail(app)


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

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Save user to CSV
        with open('data/users.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([name, email, hashed_password.decode('utf-8')])

        return redirect('/login')

    return render_template('register.html')

# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Make session permanent
        session.permanent = True

        with open('data/users.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['email'] == email and bcrypt.checkpw(password.encode('utf-8'), row['password'].encode('utf-8')):
                    # Store user in session
                    session['user_email'] = email
                    session['user_name'] = row['name']
                    # Set admin flag if email is admin@admin.com
                    session['is_admin'] = (email == 'admin@admin.com')
                    return redirect('/movies')

        return "Invalid credentials!"

    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# Browse Movies
@app.route('/movies', methods=['GET'])
def movies():
    search_query = request.args.get('search', '').lower()
    movies_list = []

    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Filter movies by title or genre
            if search_query in row['title'].lower() or search_query in row['genre'].lower():
                movies_list.append(row)
            # If no search query, display all movies
            elif not search_query:
                movies_list.append(row)

    return render_template('movies.html', movies=movies_list)


# Purchase Tickets
@app.route('/book/<movie_id>', methods=['POST'])
def book_ticket(movie_id):
    if 'user' not in session:
        return redirect('/login')

    user_email = session.get('user')  # Get the actual email address
    theater = request.form['theater']
    showtime = request.form['showtime']

    # Create a unique ticket ID
    ticket_id = f"{movie_id}-{theater}-{showtime}".replace(" ", "-")

    # Fetch movie details
    movie_title = None
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['id'] == movie_id:
                movie_title = row['title']
                ticket_price = 15
                break

    if not movie_title:
        return "Movie not found"

    # Store ticket details
    pending_ticket = {
        'ticket_id': ticket_id,
        'movie_id': movie_id,
        'theater': theater,
        'showtime': showtime,
        'user_email': user_email,
        'status': 'pending'
    }
    
    # Save pending ticket to a temporary file
    os.makedirs('data/pending_tickets', exist_ok=True)
    with open(f'data/pending_tickets/{ticket_id}.json', 'w') as f:
        json.dump(pending_ticket, f)

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"{movie_title} - {theater} ({showtime})",
                    },
                    'unit_amount': ticket_price * 100,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('payment_success', ticket_id=ticket_id, _external=True),
            cancel_url=url_for('payment_cancel', ticket_id=ticket_id, _external=True),
            metadata={'ticket_id': ticket_id}
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        if os.path.exists(f'data/pending_tickets/{ticket_id}.json'):
            os.remove(f'data/pending_tickets/{ticket_id}.json')
        return f"An error occurred: {str(e)}"
    
@app.route('/success')
def payment_success():
    ticket_id = request.args.get('ticket_id')
    if not ticket_id:
        return "No ticket ID provided"

    try:
        # Read the pending ticket
        pending_ticket_file = f'data/pending_tickets/{ticket_id}.json'
        if not os.path.exists(pending_ticket_file):
            return "Invalid or expired ticket request"
            
        with open(pending_ticket_file, 'r') as f:
            pending_ticket = json.load(f)

        # Clean up the data before writing
        clean_ticket = {
            'ticket_id': str(pending_ticket['ticket_id']).strip(),
            'movie_id': str(pending_ticket['movie_id']).strip(),
            'theater': str(pending_ticket['theater']).strip(),
            'showtime': str(pending_ticket['showtime']).strip(),
            'user_email': str(pending_ticket['user_email']).strip(),
            'status': 'confirmed'
        }

        # Write to tickets.csv with consistent formatting
        with open('data/tickets.csv', 'a', newline='') as file:
            writer = csv.writer(file)  # Use regular writer instead of DictWriter
            writer.writerow([
                clean_ticket['ticket_id'],
                clean_ticket['movie_id'],
                clean_ticket['theater'],
                clean_ticket['showtime'],
                clean_ticket['user_email'],
                clean_ticket['status']
            ])

        try:
            # Send confirmation email
            msg = Message(
                "Movie Ticket Confirmation",
                sender=app.config['MAIL_USERNAME'],
                recipients=[clean_ticket['user_email']]
            )
            
            msg.body = f"""
            Thank you for your purchase!
            
            Ticket Details:
            Ticket ID: {clean_ticket['ticket_id']}
            Movie ID: {clean_ticket['movie_id']}
            Theater: {clean_ticket['theater']}
            Showtime: {clean_ticket['showtime']}
            
            Please keep this email for your records.
            """
            
            mail.send(msg)
            print(f"Email sent successfully to {clean_ticket['user_email']}")
        except Exception as e:
            print(f"Email sending error: {e}")

        # Clean up pending ticket file
        os.remove(pending_ticket_file)
        
        return redirect('/dashboard')
    except Exception as e:
        print(f"Error in payment_success: {e}")
        return f"An error occurred: {str(e)}"

@app.route('/cancel')
def payment_cancel():
    # Clear pending ticket from session
    session.pop('pending_ticket', None)

    return "Payment canceled. No ticket was booked."

@app.route('/dashboard')
def dashboard():
    print(f"Current session: {session}")  # Debug print
    
    if 'user' not in session:
        return redirect('/login')

    user_email = session.get('user')
    user_tickets = []

    try:
        with open('data/tickets.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['user_email'].strip() == user_email.strip() and row['status'] == 'confirmed':
                    user_tickets.append(row)
                    print(f"Found ticket: {row}")  # Debug print

        return render_template('dashboard.html', tickets=user_tickets)
    except Exception as e:
        print(f"Error in dashboard: {e}")  # Debug print
        return "An error occurred while loading tickets."

# View Purchase History
@app.route('/history')
def history():  # Changed from view_history to history
    if 'user' not in session:
        return redirect('/login')

    user_email = session.get('user')
    tickets = []
    
    try:
        with open('data/tickets.csv', 'r') as file:
            reader = csv.DictReader(file, fieldnames=['ticket_id', 'movie_id', 'theater', 'showtime', 'user_email', 'status'])
            next(reader)  # Skip header row
            for row in reader:
                if row['user_email'].strip() == user_email.strip():
                    tickets.append(row)
        return render_template('history.html', tickets=tickets)
    except Exception as e:
        print(f"Error in history: {e}")
        return "An error occurred while loading ticket history."


# Admin Dashboard
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user_email' not in session or session.get('is_admin'):  # Updated admin check
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

@app.route('/movie/<movie_id>')
def movie_details(movie_id):
    if 'user' not in session:
        user_email = None
    else:
        user_email = session.get('user')

    # Get movie details
    movie = None
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['id'] == movie_id:
                movie = row
                break
    
    if not movie:
        return "Movie not found", 404

    # Get reviews for the movie
    reviews = []
    user_has_reviewed = False
    try:
        with open('data/reviews.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['movie_id'] == movie_id:
                    reviews.append(row)
                    if user_email and row['user_email'] == user_email:
                        user_has_reviewed = True
    except Exception as e:
        print(f"Error reading reviews: {e}")
        reviews = []

    # Calculate average rating
    if reviews:
        avg_rating = sum(float(review['rating']) for review in reviews) / len(reviews)
    else:
        avg_rating = 0

    return render_template('movie_details.html', 
                         movie=movie, 
                         reviews=reviews, 
                         user_has_reviewed=user_has_reviewed,
                         avg_rating=avg_rating)



@app.route('/movie/<movie_id>/review', methods=['POST'])
def submit_review(movie_id):
    if 'user' not in session:  # Changed from 'user' to 'user_email'
        return redirect('/login')

    user_email = session.get('user')  # Changed from session['user']
    rating = request.form.get('rating')
    comment = request.form.get('comment')

    # Validate input
    try:
        rating = int(rating)
        if not (1 <= rating <= 5):
            return "Rating must be between 1 and 5"
    except ValueError:
        return "Invalid rating"

    if not comment or len(comment.strip()) == 0:
        return "Comment is required"

    # Create review ID
    review_id = f"{movie_id}-{user_email}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Save review
    with open('data/reviews.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            review_id,
            movie_id,
            user_email,
            rating,
            comment,
            current_time,  # date_posted
            current_time   # date_updated
        ])

    return redirect(url_for('movie_details', movie_id=movie_id))

@app.route('/movie/<movie_id>/review/<review_id>/edit', methods=['GET', 'POST'])
def edit_review(movie_id, review_id):
    if 'user' not in session:
        return redirect('/login')

    user_email = session.get('user')

    if request.method == 'POST':
        rating = request.form.get('rating')
        comment = request.form.get('comment')

        # Validate input
        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                return "Rating must be between 1 and 5"
        except ValueError:
            return "Invalid rating"

        if not comment or len(comment.strip()) == 0:
            return "Comment is required"

        # Read all reviews
        reviews = []
        found = False
        with open('data/reviews.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['review_id'] == review_id and row['user_email'] == user_email:
                    row['rating'] = rating
                    row['comment'] = comment
                    row['date_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    found = True
                reviews.append(row)

        if not found:
            return "Review not found or unauthorized"

        # Write back all reviews
        with open('data/reviews.csv', 'w', newline='') as file:
            writer = csv.DictWriter(file, 
                fieldnames=['review_id', 'movie_id', 'user_email', 'rating', 'comment', 'date_posted', 'date_updated'])
            writer.writeheader()
            writer.writerows(reviews)

        return redirect(url_for('movie_details', movie_id=movie_id))

    # GET request - show edit form
    with open('data/reviews.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['review_id'] == review_id and row['user_email'] == user_email:
                return render_template('edit_review.html', review=row, movie_id=movie_id)

    return "Review not found or unauthorized", 404

@app.route('/admin/movies', methods=['GET', 'POST'])
def manage_movies():
    if 'user_email' not in session or session.get('user_email') != 'admin@admin.com':
        return redirect('/login')

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            # Add new movie
            id = request.form.get('id')
            title = request.form.get('title')
            genre = request.form.get('genre')
            description = request.form.get('description')
            
            with open('data/movies.csv', 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([id, title, genre, description])
            
        elif action == 'edit':
            # Edit existing movie
            id = request.form.get('id')
            title = request.form.get('title')
            genre = request.form.get('genre')
            description = request.form.get('description')
            
            movies = []
            with open('data/movies.csv', 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['id'] == id:
                        row['title'] = title
                        row['genre'] = genre
                        row['description'] = description
                    movies.append(row)
            
            with open('data/movies.csv', 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=['id', 'title', 'genre', 'description'])
                writer.writeheader()
                writer.writerows(movies)
                
        elif action == 'delete':
            # Delete movie
            id = request.form.get('id')
            movies = []
            with open('data/movies.csv', 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['id'] != id:
                        movies.append(row)
            
            with open('data/movies.csv', 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=['id', 'title', 'genre', 'description'])
                writer.writeheader()
                writer.writerows(movies)

        return redirect('/admin/movies')

    # GET request - show movie list
    movies = []
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        movies = list(reader)

    return render_template('admin/manage_movies.html', movies=movies)
# -------------------- Helper Functions --------------------
# Ensure data directory exists
def ensure_data_files():
    # Create all necessary directories
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/pending_tickets', exist_ok=True)
    os.makedirs('static', exist_ok=True)  # Create static directory if it doesn't exist
    os.makedirs('static/barcodes', exist_ok=True)  # Create barcodes directory if it doesn't exist

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
            writer.writerow(['ticket_id', 'movie_id', 'theater', 'showtime', 'user_email', 'status'])

    if not os.path.exists('data/reviews.csv'):
        with open('data/reviews.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['review_id', 'movie_id', 'user_email', 'rating', 'comment', 'date_posted', 'date_updated'])

def update_movies_with_ids():
    movies = []
    needs_update = False
    
    # Read existing movies
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames
        if 'id' not in headers:
            needs_update = True
        
        for i, row in enumerate(reader, 1):
            if needs_update:
                row['id'] = str(i)
            movies.append(row)
    
    # If we need to add IDs, rewrite the file
    if needs_update:
        with open('data/movies.csv', 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=['id', 'title', 'genre', 'description'])
            writer.writeheader()
            writer.writerows(movies)
# Initialize data files
ensure_data_files()
update_movies_with_ids()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)