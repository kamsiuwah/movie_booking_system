from flask import Flask, render_template, request, redirect, session, url_for, jsonify, make_response, flash
import csv
import os
import bcrypt
import stripe
import json
import jwt
import datetime
from functools import wraps
from datetime import timedelta
import barcode
from barcode.writer import ImageWriter
from flask_mail import Mail, Message



app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Required for session management
stripe.api_key = 'sk_test_51QRlQkCV3XkBzb7OlrDP3tHy8TrtvEwvjcbT3rMsxApUuLceTPNs5dRAHkJpg0J6zWDVtDOHCsWvPKLmu0o3dRn600OmSzOZTA'
# Add these constants at the top of your file
JWT_SECRET_KEY = 'your-secret-key-here'  # In production, use a secure secret key
JWT_ALGORITHM = 'HS256'
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
    # Get latest movies
    latest_movies = []
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        movies = list(reader)
        latest_movies = movies[:4]  # Get first 4 movies for latest releases
        upcoming_movies = movies[4:8]  # Get next 4 movies for upcoming releases
    
    return render_template('index.html', 
                         latest_movies=latest_movies,
                         upcoming_movies=upcoming_movies)

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
# Create a decorator to check for valid JWT token
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token')

        if not token:
            return redirect('/login')

        try:
            data = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            session['user_email'] = data['user_email']
            session['user_name'] = data['user_name']
            session['is_admin'] = data['is_admin']
        except:
            return redirect('/login')

        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check both is_admin flag and specific admin email
        if not session.get('is_admin') or session.get('user_email') != 'admin@admin.com':
            flash('Admin access required', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with open('data/users.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['email'] == email and bcrypt.checkpw(password.encode('utf-8'), row['password'].encode('utf-8')):
                    token = jwt.encode({
                        'user_email': email,
                        'user_name': row['name'],
                        'is_admin': (email == 'admin@admin.com'),
                        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
                    }, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

                    response = make_response(redirect('/movies'))
                    response.set_cookie(
                        'token',
                        token,
                        httponly=True,
                        secure=False,  # Set to True in production with HTTPS
                        samesite='Lax',
                        max_age=60*60*24*7  # 7 days
                    )
                    
                    # Set session variables
                    session['user_email'] = email
                    session['user_name'] = row['name']
                    session['is_admin'] = (email == 'admin@admin.com')
                    
                    return response

        return "Invalid credentials!", 401

    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    response = make_response(redirect('/'))
    response.delete_cookie('token')
    session.clear()
    return response

def get_theater_names():
    theater_names = {}
    try:
        with open('data/theaters.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                theater_names[row['id']] = f"{row['name']} ({row['location']})"
    except Exception as e:
        print(f"Error loading theaters: {e}")
    return theater_names

@app.route('/movies', methods=['GET'])
def movies():
    search_query = request.args.get('search', '').lower()
    movies_list = []
    theater_names = get_theater_names()

    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if search_query in row['title'].lower() or search_query in row['genre'].lower():
                movies_list.append(row)
            elif not search_query:
                movies_list.append(row)

    return render_template('movies.html', 
                         movies=movies_list,
                         theater_names=theater_names)

@app.route('/movie/<movie_id>')
def movie_details(movie_id):
    user_email = session.get('user_email')
    theater_names = get_theater_names()

    # Get movie details
    movie = None
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['id'] == movie_id:
                movie = row
                break
    
    if not movie:
        flash('Movie not found', 'error')
        return redirect(url_for('movies'))

    # Get reviews
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

    # Calculate average rating
    avg_rating = sum(float(review['rating']) for review in reviews) / len(reviews) if reviews else 0

    return render_template('movie_details.html', 
                         movie=movie, 
                         reviews=reviews, 
                         user_has_reviewed=user_has_reviewed,
                         avg_rating=avg_rating,
                         theater_names=theater_names)
# Purchase Tickets
@app.route('/book/<movie_id>', methods=['POST'])
@token_required
def book_ticket(movie_id):
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session.get('user_email')
    theater = request.form['theater']
    showtime = request.form['showtime']
    quantity = int(request.form.get('quantity', 1))

    # Check ticket limit
    if quantity > 10:
        flash('Maximum 10 tickets per booking allowed', 'error')
        return redirect(url_for('movie_details', movie_id=movie_id))

    # Fetch and validate movie details
    movie = None
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['id'] == movie_id:
                movie = row
                break

    if not movie:
        flash('Movie not found', 'error')
        return redirect(url_for('movies'))

    # Validate theater and showtime
    theaters = movie['theaters'].split('|')
    showtimes = movie['showtimes'].split('|')

    if theater not in theaters:
        flash('Invalid theater selection', 'error')
        return redirect(url_for('movie_details', movie_id=movie_id))

    if showtime not in showtimes:
        flash('Invalid showtime selection', 'error')
        return redirect(url_for('movie_details', movie_id=movie_id))

    # Create a unique ticket ID
    ticket_id = f"{movie_id}-{theater}-{showtime}".replace(" ", "-")
    ticket_price = 15  # You might want to store this in the movie data or a separate configuration

    # Store ticket details
    pending_ticket = {
        'ticket_id': ticket_id,
        'movie_id': movie_id,
        'theater': theater,
        'showtime': showtime,
        'user_email': user_email,
        'quantity': quantity,
        'status': 'pending'
    }
    
    # Save pending ticket to a temporary file
    os.makedirs('data/pending_tickets', exist_ok=True)
    with open(f'data/pending_tickets/{ticket_id}.json', 'w') as f:
        json.dump(pending_ticket, f)

    try:
        # Create Stripe checkout session with quantity
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"{movie['title']} - {theater} ({showtime})",
                    },
                    'unit_amount': ticket_price * 100,
                },
                'quantity': quantity,
            }],
            mode='payment',
            success_url=url_for('payment_success', ticket_id=ticket_id, _external=True),
            cancel_url=url_for('payment_cancel', ticket_id=ticket_id, _external=True),
            metadata={
                'ticket_id': ticket_id,
                'quantity': str(quantity)
            }
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        if os.path.exists(f'data/pending_tickets/{ticket_id}.json'):
            os.remove(f'data/pending_tickets/{ticket_id}.json')
        flash('An error occurred during payment processing', 'error')
        return redirect(url_for('movie_details', movie_id=movie_id))
    
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
            'quantity': int(pending_ticket.get('quantity', 1)),
            'status': 'confirmed'
        }

        # Write to tickets.csv with consistent formatting
        with open('data/tickets.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                clean_ticket['ticket_id'],
                clean_ticket['movie_id'],
                clean_ticket['theater'],
                clean_ticket['showtime'],
                clean_ticket['user_email'],
                clean_ticket['quantity'],
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
            Quantity: {clean_ticket['quantity']}
            
            Please keep this email for your records.
            """
            
            mail.send(msg)
            print(f"Email sent successfully to {clean_ticket['user_email']}")
        except Exception as e:
            print(f"Email sending error: {e}")

        # Clean up pending ticket file
        os.remove(pending_ticket_file)
        
        flash('Tickets booked successfully!', 'success')
        return redirect('/dashboard')
    except Exception as e:
        print(f"Error in payment_success: {e}")
        flash('An error occurred processing your payment', 'error')
        return redirect('/movies')
@app.route('/cancel')
def payment_cancel():
    # Clear pending ticket from session
    session.pop('pending_ticket', None)

    return "Payment canceled. No ticket was booked."

@app.route('/dashboard')
@token_required
def dashboard():
    user_email = session.get('user_email')
    is_admin = session.get('is_admin', False)
    
    # Get user's recent tickets
    recent_tickets = []
    try:
        with open('data/tickets.csv', 'r') as file:
            reader = csv.DictReader(file)
            tickets = [row for row in reader if row['user_email'] == user_email]
            recent_tickets = sorted(tickets, key=lambda x: x['ticket_id'], reverse=True)[:3]
    except Exception as e:
        print(f"Error loading tickets: {e}")
    
    # Get current movies
    current_movies = []
    try:
        with open('data/movies.csv', 'r') as file:
            reader = csv.DictReader(file)
            current_movies = list(reader)[:3]
    except Exception as e:
        print(f"Error loading movies: {e}")

    return render_template('dashboard.html',
                         recent_tickets=recent_tickets,
                         current_movies=current_movies,
                         is_admin=is_admin)
# View Purchase History
@app.route('/history')
@token_required
def history():
    user_email = session.get('user_email')
    tickets = []
    
    try:
        with open('data/tickets.csv', 'r') as file:
            reader = csv.DictReader(file, fieldnames=['ticket_id', 'movie_id', 'theater', 'showtime', 'user_email', 'status'])
            next(reader)
            for row in reader:
                if row['user_email'].strip() == user_email.strip():
                    tickets.append(row)
        return render_template('history.html', tickets=tickets)
    except Exception as e:
        print(f"Error in history: {e}")
        return "An error occurred while loading ticket history."


# Admin Dashboard
@app.route('/admin')
@token_required
@admin_required
def admin_dashboard():
    return redirect(url_for('manage_movies'))


@app.route('/movie/<movie_id>/review', methods=['POST'])
@token_required
def submit_review(movie_id):
    if 'user_email' not in session:  # Changed from 'user' to 'user_email'
        return redirect('/login')

    user_email = session.get('user_email')  # Changed from session['user']
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
@token_required
@admin_required
def manage_movies():
    # Get all theaters for the form
    all_theaters = []
    theater_names = {}
    with open('data/theaters.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            all_theaters.append(row)
            theater_names[row['id']] = f"{row['name']} ({row['location']})"

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            # Generate new ID
            with open('data/movies.csv', 'r') as file:
                reader = csv.DictReader(file)
                existing_ids = [int(row['id']) for row in reader if row['id'].isdigit()]
                new_id = str(max(existing_ids + [0]) + 1)
            
            # Get form data
            title = request.form.get('title')
            genre = request.form.get('genre')
            description = request.form.get('description')
            theaters = '|'.join(request.form.getlist('theaters'))
            showtimes = '|'.join(request.form.getlist('showtimes'))
            
            # Add new movie
            with open('data/movies.csv', 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([new_id, title, genre, description, theaters, showtimes])
            
            flash('Movie added successfully!', 'success')
            
        elif action == 'edit':
            id = request.form.get('id')
            title = request.form.get('title')
            genre = request.form.get('genre')
            description = request.form.get('description')
            theaters = '|'.join(request.form.getlist('theaters'))
            showtimes = '|'.join(request.form.getlist('showtimes'))
            
            # Update movie
            movies = []
            with open('data/movies.csv', 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['id'] == id:
                        row.update({
                            'title': title,
                            'genre': genre,
                            'description': description,
                            'theaters': theaters,
                            'showtimes': showtimes
                        })
                    movies.append(row)
            
            with open('data/movies.csv', 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=['id', 'title', 'genre', 'description', 'theaters', 'showtimes'])
                writer.writeheader()
                writer.writerows(movies)
            
            flash('Movie updated successfully!', 'success')
        
        elif action == 'delete':
            id = request.form.get('id')
            movies = []
            with open('data/movies.csv', 'r') as file:
                reader = csv.DictReader(file)
                movies = [row for row in reader if row['id'] != id]
            
            with open('data/movies.csv', 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=['id', 'title', 'genre', 'description', 'theaters', 'showtimes'])
                writer.writeheader()
                writer.writerows(movies)
            
            flash('Movie deleted successfully!', 'success')

    # Get updated movie list
    movies = []
    with open('data/movies.csv', 'r') as file:
        reader = csv.DictReader(file)
        movies = list(reader)

    return render_template('admin/manage_movies.html', 
                         movies=movies,
                         all_theaters=all_theaters,
                         theater_names=theater_names)

@app.route('/admin/theaters', methods=['GET', 'POST'])
@token_required
@admin_required
def manage_theaters():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            # Generate new ID
            with open('data/theaters.csv', 'r') as file:
                reader = csv.DictReader(file)
                existing_ids = [int(row['id']) for row in reader if row['id'].isdigit()]
                new_id = str(max(existing_ids + [0]) + 1)
            
            name = request.form.get('name')
            location = request.form.get('location')
            capacity = request.form.get('capacity')
            screens = request.form.get('screens')
            amenities = request.form.get('amenities').replace(',', '|')
            
            with open('data/theaters.csv', 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([new_id, name, location, capacity, screens, amenities])
            
            flash('Theater added successfully!', 'success')
            
        elif action == 'edit':
            id = request.form.get('id')
            name = request.form.get('name')
            location = request.form.get('location')
            capacity = request.form.get('capacity')
            screens = request.form.get('screens')
            amenities = request.form.get('amenities').replace(',', '|')
            
            theaters = []
            with open('data/theaters.csv', 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['id'] == id:
                        row.update({
                            'name': name,
                            'location': location,
                            'capacity': capacity,
                            'screens': screens,
                            'amenities': amenities
                        })
                    theaters.append(row)
            
            with open('data/theaters.csv', 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=['id', 'name', 'location', 'capacity', 'screens', 'amenities'])
                writer.writeheader()
                writer.writerows(theaters)
            
            flash('Theater updated successfully!', 'success')
                
        elif action == 'delete':
            id = request.form.get('id')
            theaters = []
            with open('data/theaters.csv', 'r') as file:
                reader = csv.DictReader(file)
                theaters = [row for row in reader if row['id'] != id]
            
            with open('data/theaters.csv', 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=['id', 'name', 'location', 'capacity', 'screens', 'amenities'])
                writer.writeheader()
                writer.writerows(theaters)
            
            flash('Theater deleted successfully!', 'success')

    # Get updated theater list
    theaters = []
    with open('data/theaters.csv', 'r') as file:
        reader = csv.DictReader(file)
        theaters = list(reader)

    return render_template('admin/manage_theaters.html', theaters=theaters)

@app.route('/admin/reports')
@token_required
@admin_required
def admin_reports():
    try:
        # Get total number of tickets sold
        ticket_sales = 0
        tickets_by_movie = {}
        tickets_by_theater = {}
        
        with open('data/tickets.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['status'] == 'confirmed':
                    ticket_sales += 1
                    
                    # Count tickets per movie
                    movie_id = row['movie_id']
                    tickets_by_movie[movie_id] = tickets_by_movie.get(movie_id, 0) + 1
                    
                    # Count tickets per theater
                    theater = row['theater']
                    tickets_by_theater[theater] = tickets_by_theater.get(theater, 0) + 1
        
        # Get movie details for the report
        movies_data = {}
        with open('data/movies.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                movies_data[row['id']] = row['title']
        
        # Format movie sales data
        movie_sales = []
        for movie_id, count in tickets_by_movie.items():
            movie_title = movies_data.get(movie_id, f"Unknown Movie ({movie_id})")
            movie_sales.append({
                'title': movie_title,
                'tickets_sold': count
            })
        
        # Get theater sales data
        theater_sales = []
        for theater, count in tickets_by_theater.items():
            theater_sales.append({
                'theater': theater,
                'tickets_sold': count
            })
        
        # Sort by tickets sold
        movie_sales.sort(key=lambda x: x['tickets_sold'], reverse=True)
        theater_sales.sort(key=lambda x: x['tickets_sold'], reverse=True)
        
        # Get currently playing movies
        current_movies = []
        with open('data/movies.csv', 'r') as file:
            reader = csv.DictReader(file)
            current_movies = list(reader)

        return render_template('admin/reports.html',
                             total_tickets=ticket_sales,
                             movie_sales=movie_sales,
                             theater_sales=theater_sales,
                             current_movies=current_movies)
                             
    except Exception as e:
        print(f"Error generating report: {e}")
        flash('Error generating report', 'error')
        return redirect(url_for('admin_dashboard'))
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
            writer.writerow(['ticket_id', 'movie_id', 'theater', 'showtime', 'user_email', 'quantity', 'status'])

    if not os.path.exists('data/reviews.csv'):
        with open('data/reviews.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['review_id', 'movie_id', 'user_email', 'rating', 'comment', 'date_posted', 'date_updated'])
    if not os.path.exists('data/theaters.csv'):
        with open('data/theaters.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'location', 'capacity', 'screens', 'amenities'])

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