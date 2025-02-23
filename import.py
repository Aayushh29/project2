import csv
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

# Set up database connection
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def import_books():
    with open("books.csv", "r") as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        for isbn, title, author, year in reader:
            db.execute(text("INSERT INTO  books(isbn, title, author, year) VALUES (:isbn, :title, :author, :year)"), 
                       {"isbn": isbn, "title": title, "author": author, "year": int(year)})
        db.commit()

if __name__ == "__main__":
    import_books()
    print("Books imported successfully.")