import os
from flask import Flask, render_template, request, redirect, session, jsonify
from flask import Flask, render_template, request, redirect, session, jsonify, flash
from flask_session import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
import requests

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        db.execute(text("INSERT INTO users (username, password) VALUES (:username, :password)"), 
                   {"username": username, "password": password})
        db.commit()
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = db.execute(text("SELECT * FROM users WHERE username = :username"), {"username": username}).fetchone()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.username
            return redirect("/search")
        return "Invalid credentials!"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/search", methods=["GET"])
def search():
    if "user_id" not in session:
        return redirect("/login")

    query = request.args.get("query", "")
    books = db.execute(text("SELECT * FROM books WHERE title ILIKE :query OR author ILIKE :query OR isbn ILIKE :query"),
                       {"query": f"%{query}%"}).fetchall()
    return render_template("search.html", books=books)

@app.route("/book/<isbn>", methods=["GET", "POST"])
def book(isbn):
    if "user_id" not in session:
        return redirect("/login")

    book = db.execute(text("SELECT * FROM books WHERE isbn = :isbn"), {"isbn": isbn}).fetchone()
    reviews = db.execute(text("SELECT * FROM reviews WHERE book_isbn = :isbn"), {"isbn": isbn}).fetchall()
    show_rev_section = db.execute(text("SELECT * FROM reviews WHERE book_isbn = :isbn AND user_id = :user_id"),
    {"isbn": isbn, "user_id": session["user_id"]}).fetchone()  # Use fetchone() to check if a review exists

    # Fetch Google Books and OpenLibrary data with error handling
    google_data, openlibrary_data = {}, {}
    google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    openlibrary_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"

    try:
        google_response = requests.get(google_url)
        if google_response.status_code == 200:
            google_data = google_response.json().get("items", [{}])[0].get("volumeInfo", {})
    except (requests.exceptions.RequestException, ValueError):
        google_data = {}

    try:
        openlibrary_response = requests.get(openlibrary_url)
        if openlibrary_response.status_code == 200:
            openlibrary_data = openlibrary_response.json().get(f"ISBN:{isbn}", {})
    except (requests.exceptions.RequestException, ValueError):
        openlibrary_data = {}

    google_rating = google_data.get("averageRating", "No Rating")
    openlibrary_rating = openlibrary_data.get("average_rating", "No Rating")
    book_image = google_data.get("imageLinks", {}).get("thumbnail", "https://via.placeholder.com/150")
    google_book = {
        "title": google_data.get("title", book.title),
        "authors": google_data.get("authors", [book.author])
    }
    gemini_summary = get_book_summary('The Dark Is Rising')
    
    if request.method == "POST":
        review = request.form["review"]
        rating = request.form["rating"]
        if show_rev_section:
            flash("You have already submitted a review for this book!", "danger")
            return redirect(f"/book/{isbn}")
        
        db.execute(text("""
            INSERT INTO reviews (user_id, book_isbn, review, rating) 
            VALUES (:user_id, :isbn, :review, :rating) 
        """),
        {"user_id": session["user_id"], "isbn": isbn, "review": review, "rating": rating})
        db.commit()
        flash("Review submitted successfully!", "success")
        return redirect(f"/book/{isbn}")

    return render_template("book.html", book=book, reviews=reviews, google_book=google_book, google_rating=google_rating, openlibrary_rating=openlibrary_rating, book_image=book_image, gemini_summary=gemini_summary, show_rev_section = show_rev_section)

@app.route("/api/book/<isbn>")
def api_book(isbn):
    # Fetch book from local database
    book_row = db.execute(
        text("SELECT title, author, year, isbn FROM books WHERE isbn = :isbn"),
        {"isbn": isbn}
    ).fetchone()

    if not book_row:
        return jsonify({"error": "Book not found"}), 404

    # Convert tuple to dictionary manually
    book = {
        "title": book_row[0],
        "author": book_row[1],
        "publishedDate": book_row[2],
        "ISBN_10": book_row[3],
        "ISBN_13": None  # Placeholder, fetched from API later
    }

    # Fetch reviews
    reviews = db.execute(
        text("SELECT rating FROM reviews WHERE book_isbn = :isbn"),
        {"isbn": isbn}
    ).fetchall()
    review_count = len(reviews)
    avg_rating = sum(r[0] for r in reviews) / review_count if review_count else None

    # Fetch additional data from Google Books API
    google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    google_data = {}

    try:
        google_response = requests.get(google_url)
        if google_response.status_code == 200:
            google_data = google_response.json().get("items", [{}])[0].get("volumeInfo", {})
    except requests.exceptions.RequestException:
        google_data = {}

    # Extract ISBN-13 if available
    isbn_13 = None
    industry_ids = google_data.get("industryIdentifiers", [])
    for identifier in industry_ids:
        if identifier["type"] == "ISBN_13":
            isbn_13 = identifier["identifier"]
    
    book["ISBN_13"] = isbn_13  # Update ISBN_13 in the book dictionary
    book["description"] = google_data.get("description", None)
    book["reviewCount"] = review_count
    book["averageRating"] = avg_rating
    book["summarizedDescription"] = get_book_summary(book["title"])

    return jsonify(book)
 
# Fetch book ratings from Google Books API
def get_google_books_rating(isbn):
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    response = requests.get(url)
    data = response.json()
    if "items" in data:
        book_info = data["items"][0]["volumeInfo"]
        return book_info.get("averageRating", "No rating available")
    return "No rating available"

# Fetch book summary from Google's Gemini API
def get_book_summary(title):
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: API key not set."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Summarize the book '{title}' in less than 50 words."
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Extract summary properly
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                summary = parts[0].get("text", "No summary available")

                # Limit to 50 words instead of characters
                words = summary.split()
                return " ".join(words[:50])  # Ensure it's under 50 words
            
        return "No summary available."
    
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}"
if __name__ == "__main__":
    app.run(debug=True)
