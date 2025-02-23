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

    if request.method == "POST":
        review_text = request.form["review"]
        rating = request.form["rating"]

        db.execute(text("""
            INSERT INTO reviews (user_id, book_isbn, review, rating) 
            VALUES (:user_id, :isbn, :review, :rating) 
        """),
        {"user_id": session["user_id"], "isbn": isbn, "review": review_text, "rating": rating})
        db.commit()
        flash("Review submitted successfully!", "success")
        return redirect(f"/book/{isbn}")

    return render_template("book.html", book=book, reviews=reviews, google_book=google_book, google_rating=google_rating, openlibrary_rating=openlibrary_rating, book_image=book_image)

@app.route("/api/book/<isbn>")
def api_book(isbn):
    book = db.execute(text("SELECT * FROM books WHERE isbn = :isbn"), {"isbn": isbn}).fetchone()
    if not book:
        return jsonify({"error": "Book not found"}), 404

    reviews = db.execute(text("SELECT rating FROM reviews WHERE book_isbn = :isbn"), {"isbn": isbn}).fetchall()
    avg_rating = sum(r["rating"] for r in reviews) / len(reviews) if reviews else None

    google_rating = "No Rating"
    google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    try:
        google_response = requests.get(google_url)
        if google_response.status_code == 200:
            google_data = google_response.json()
            google_rating = google_data.get("items", [{}])[0].get("volumeInfo", {}).get("averageRating", "No Rating")
    except (requests.exceptions.RequestException, ValueError):
        google_rating = "No Rating"

    openlibrary_rating = "No Rating"
    openlibrary_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        openlibrary_response = requests.get(openlibrary_url)
        if openlibrary_response.status_code == 200:
            openlibrary_data = openlibrary_response.json()
            book_data = openlibrary_data.get(f"ISBN:{isbn}", {})
            openlibrary_rating = book_data.get("average_rating", "No Rating")
    except (requests.exceptions.RequestException, ValueError):
        openlibrary_rating = "No Rating"

    return jsonify({
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "average_rating": avg_rating,
        "google_rating": google_rating,
        "openlibrary_rating": openlibrary_rating,
        "review_count": len(reviews)
    })

if __name__ == "__main__":
    app.run(debug=True)
