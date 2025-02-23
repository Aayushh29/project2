# Book Review Website

## Overview
This is a **Book Review Web Application** that allows users to **register, log in, search for books, leave reviews, and view book ratings** from both **Google Books API** and **OpenLibrary API**. The platform is designed to provide a seamless experience for users looking to explore book details and share their thoughts on various books.

## Features
- **User Registration & Authentication**
  - Users can sign up and log in using a secure authentication system.
  - Passwords are stored securely using hashing.

- **Book Search**
  - Users can search for books using **ISBN, title, or author**.
  - Results are displayed dynamically.

- **Book Details & Ratings**
  - Each book has a dedicated page displaying its **title, author, year, and ISBN**.
  - Ratings from **Google Books API** and **OpenLibrary API** are fetched and displayed.
  - Book cover images are retrieved from Google Books.

- **User Reviews**
  - Users can leave a review and rate books (1-5 stars).
  - Reviews are stored in a **PostgreSQL database**.
  - If a review already exists, the system **updates** the previous review.

- **API Access**
  - Users can programmatically access **book details and reviews** via the `/api/book/<isbn>` endpoint.

## Technologies Used
- **Backend**: Flask (Python), Flask-Session, SQLAlchemy (raw SQL queries)
- **Database**: PostgreSQL
- **Frontend**: HTML, CSS (Bootstrap-based styling)
- **APIs**: Google Books API, OpenLibrary API

## Setup Instructions
### 1. Install Dependencies
```sh
pip install -r requirements.txt
```

### 2. Set Up Database
Ensure you have PostgreSQL installed. Set up the database by running:
```sh
export DATABASE_URL='your_database_url_here'
```
Then, create the necessary tables by executing the migration script (if applicable).

### 3. Import Books Dataset
Run the following command to import book data into the database:
```sh
python import.py
```

### 4. Run the Web Application
```sh
python application.py
```
The application will be available at **http://127.0.0.1:5000/**.

## API Usage
### Fetch Book Details
**Endpoint:**
```
GET /api/book/<isbn>
```
**Response:**
```json
{
  "title": "Example Book Title",
  "author": "Author Name",
  "year": 2022,
  "isbn": "1234567890",
  "average_rating": 4.5,
  "google_rating": 4.0,
  "openlibrary_rating": 3.9,
  "review_count": 5
}
```

## Notes
- All database interactions use **raw SQL commands** (no ORM).
- The project follows **MVC structure** for clean separation of concerns.

## License
This project is open-source and available for modification and enhancement. Feel free to contribute!
