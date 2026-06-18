"""
seed.py — Populate the database with test data.

Run this script to reset the database and load sample users and messages.
Useful for manual testing of the CLI client.

HOW TO RUN:
  python seed.py

WHAT IT DOES:
  1. Deletes all existing data (fresh start)
  2. Creates 3 test users: alice, bob, charlie
  3. Sends messages between them
  4. Prints the results

SAFE TO RUN MULTIPLE TIMES:
  Each run resets the database, so you can safely run this
  whenever you want to reset to a known state.
"""

from server.models import User, Message, get_db, create_tables, engine, Base
from server.auth import hash_password
from server.crypto import encrypt
from sqlalchemy.orm import sessionmaker

print("🌱 Seeding database...")

# Create fresh tables
print("  Creating tables...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

# Create session
Session = sessionmaker(bind=engine)
db = Session()

try:
    # Create users
    print("  Creating users...")
    users = {
        "alice": User(username="alice", password_hash=hash_password("alice123")),
        "bob": User(username="bob", password_hash=hash_password("bob123")),
        "charlie": User(username="charlie", password_hash=hash_password("charlie123")),
    }
    
    for user in users.values():
        db.add(user)
    db.commit()
    
    # Create messages
    print("  Creating messages...")
    messages = [
        Message(
            sender="alice",
            recipient="bob",
            ciphertext=encrypt("Hey Bob! Are you there?")
        ),
        Message(
            sender="bob",
            recipient="alice",
            ciphertext=encrypt("Hi Alice! Just arrived, what's up?")
        ),
        Message(
            sender="alice",
            recipient="bob",
            ciphertext=encrypt("Great! Let's sync later today.")
        ),
        Message(
            sender="charlie",
            recipient="bob",
            ciphertext=encrypt("Bob, can you review my code?")
        ),
        Message(
            sender="bob",
            recipient="charlie",
            ciphertext=encrypt("Sure, send it over!")
        ),
    ]
    
    for msg in messages:
        db.add(msg)
    db.commit()
    
    print("\n✓ Database seeded successfully!")
    print(f"  Created {len(users)} users: {', '.join(users.keys())}")
    print(f"  Created {len(messages)} messages")
    print("\nYou can now run the CLI client:")
    print("  python -m client.client")
    
finally:
    db.close()
