# Secure Messenger

A secured REST API for private messaging with end-to-end encryption and JWT authentication.

## Stage 1: The Foundation

By the end of Stage 1, users can register, login, send encrypted messages, and read them back. No real-time yet — that is Stage 2. Just a solid, secure backend.

## Features

- **User Authentication**: Registration and login with bcrypt password hashing
- **JWT Tokens**: Secure token-based authentication with expiration
- **Encrypted Messaging**: End-to-end encryption for all messages
- **Message Storage**: SQLAlchemy ORM with SQLite database
- **API Security**: Bearer token authentication on protected routes

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd secure-messenger
```

2. Create a virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate  # On Windows
source .venv/bin/activate  # On macOS/Linux
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

Start the development server:
```bash
uvicorn server.main:app --reload
```

The API will be available at `http://localhost:8000`

Access the interactive API documentation at `http://localhost:8000/docs`

## API Endpoints

### Authentication

#### Register
- **POST** `/register`
- **Body**: `{ "username": "alice", "password": "secret123" }`
- **Response**: `{ "message": "User registered successfully" }`

#### Login
- **POST** `/login`
- **Body**: `{ "username": "alice", "password": "secret123" }`
- **Response**: `{ "access_token": "eyJhbGc...", "token_type": "bearer" }`

### Messaging

All messaging endpoints require a Bearer token in the Authorization header:
```
Authorization: Bearer <access_token>
```

#### Send Message
- **POST** `/send`
- **Body**: `{ "recipient": "bob", "content": "Hello Bob!" }`
- **Response**: 
```json
{
  "id": 1,
  "sender": "alice",
  "recipient": "bob",
  "content": "Hello Bob!",
  "created_at": "2026-05-07T10:30:00+00:00"
}
```

#### Get Messages
- **GET** `/messages`
- **Response**: List of all messages (sent and received)
```json
[
  {
    "id": 1,
    "sender": "alice",
    "recipient": "bob",
    "content": "Hello Bob!",
    "created_at": "2026-05-07T10:30:00+00:00"
  }
]
```

## Project Structure

```
secure-messenger/
├── server/
│   ├── __init__.py
│   ├── main.py           # FastAPI app initialization
│   ├── auth.py           # Authentication functions (hashing, JWT, verification)
│   ├── crypto.py         # Encryption/decryption functions
│   ├── models.py         # SQLAlchemy models (User, Message)
│   ├── schemas.py        # Pydantic request/response schemas
│   └── routes.py         # API endpoint definitions
├── tests/
│   ├── __init__.py
│   └── test_app.py       # Unit tests
├── requirements.txt      # Project dependencies
├── STAGE_1.md           # Stage 1 specifications
└── README.md            # This file
```

## Security Features

### Password Storage
- Passwords are hashed using **bcrypt** with salt
- Plain text passwords are never stored in the database
- Even the system cannot recover the original password

### JWT Tokens
- Tokens are signed with a secret key
- Include expiration time (configurable)
- Bearer token authentication on protected routes

### Message Encryption
- All messages are encrypted before storage
- Only the ciphertext is stored in the database
- Decrypted on retrieval for the client

## Testing

Run the test suite:
```bash
pytest tests/
```

## Environment Variables

Create a `.env` file if you need to customize:
- `SECRET_KEY`: JWT signing key (auto-generated if not set)
- `TOKEN_EXPIRE_HOURS`: JWT token expiration time (default: 24)
- `DATABASE_URL`: SQLite database path (default: `sqlite:///messages.db`)

## What's Next

**Stage 2**: Real-time messaging with WebSockets for live conversations.

## License

MIT
