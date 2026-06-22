# Secure Messenger

A real-time encrypted messaging platform with end-to-end encryption, JWT authentication, and instant message delivery via Server-Sent Events (SSE).

## Features

- **User Authentication**: Registration and login with bcrypt password hashing
- **JWT Tokens**: Secure token-based authentication (24-hour expiry)
- **Encrypted Messaging**: AES-256-GCM encryption for all stored messages
- **Message Storage**: SQLAlchemy ORM with SQLite
- **Real-Time Delivery**: Server-Sent Events (SSE) — no polling
- **Web UI**: Browser-based chat interface served at `/`
- **CLI Client**: Interactive terminal client
- **Emotion Camera**: Webcam-based emotion detection that inserts emoji into messages (requires a separate emotion service at `http://localhost:5001`)

## Installation

### Prerequisites
- Python 3.8+

### Setup

```bash
git clone <repository-url>
cd secure-messenger
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

## Running

### Server
```bash
uvicorn server.main:app --reload
```

- API + Web UI: `http://localhost:8000`
- Interactive API docs: `http://localhost:8000/docs`

### CLI Client (optional)
```bash
python -m client.client
```

### Seed Test Data
```bash
python seed.py
```

Creates three test users:
- `alice` / `alice123`
- `bob` / `bob123`
- `charlie` / `charlie123`

## API Endpoints

### Authentication

#### Register
- **POST** `/register`
- **Body**: `{ "username": "alice", "password": "secret123" }` (username ≥ 3 chars, password ≥ 6 chars)
- **Response**: `{ "message": "User registered successfully" }`

#### Login
- **POST** `/login`
- **Body**: `{ "username": "alice", "password": "secret123" }`
- **Response**: `{ "access_token": "eyJhbGc...", "token_type": "bearer" }`

### Messaging

All messaging endpoints require a Bearer token:
```
Authorization: Bearer <access_token>
```

#### Send Message
- **POST** `/messages`
- **Body**: `{ "recipient": "bob", "content": "Hello Bob!" }`
- **Response**:
```json
{
  "id": 1,
  "sender": "alice",
  "recipient": "bob",
  "content": "Hello Bob!",
  "created_at": "2026-05-27T10:30:00+00:00"
}
```

#### Get Messages
- **GET** `/messages`
- Returns only messages where the authenticated user is the sender or recipient.

#### Stream Messages (Real-Time)
- **GET** `/stream`
- Opens a persistent SSE connection. Messages are pushed instantly as they are sent.
- Auth via header: `Authorization: Bearer <token>`
- Auth via query param: `?token=<token>` (required for browser `EventSource`)

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/stream
```

Messages arrive as:
```
data: {"id":1,"sender":"alice","recipient":"bob","content":"Hello!","created_at":"..."}
```

#### Web UI
- **GET** `/`
- Serves the browser-based chat interface.

## Project Structure

```
secure-messenger/
├── server/
│   ├── main.py          # FastAPI app, lifespan, router registration, serves /
│   ├── routes.py        # All API route handlers
│   ├── auth.py          # bcrypt hashing, JWT creation/validation, auth dependencies
│   ├── crypto.py        # AES-256-GCM encrypt/decrypt
│   ├── broadcaster.py   # SSE fan-out manager
│   ├── models.py        # SQLAlchemy models (User, Message) + DB setup
│   └── schemas.py       # Pydantic request/response schemas
├── client/
│   └── client.py        # Interactive CLI client
├── emotion-service/
│   ├── app.py           # Flask emotion detection microservice (DeepFace)
│   └── requirements.txt
├── static/
│   └── index.html       # Browser chat UI with emotion camera feature
├── tests/
│   └── test_app.py      # 23 tests (auth, encryption, messaging, SSE)
├── requirements.txt
├── seed.py              # Populates DB with sample users and messages
└── README.md
```

## Security

- Passwords hashed with **bcrypt** (never stored in plain text)
- JWT tokens signed with HS256, expire after 24 hours
- Messages encrypted with **AES-256-GCM** before storage; only ciphertext in DB
- Fresh random nonce per message — identical messages produce different ciphertexts
- Tampered ciphertext raises an exception on decryption
- `/stream` requires a valid JWT (header or query param)
- Users can only retrieve messages they sent or received

## Design Decisions & Trade-offs

Why each technology was chosen, and what a production version would need to change:

- **bcrypt (not SHA-256/MD5) for passwords** — bcrypt is *intentionally slow* and salted per-password, so a leaked database is expensive to brute-force. Fast hashes like SHA-256 are designed for speed, which is exactly wrong for password storage.
- **AES-256-GCM (not AES-CBC) for messages** — GCM is *authenticated* encryption: it gives confidentiality **and** integrity, so any tampering with a stored blob fails decryption instead of returning garbage. A fresh 12-byte nonce per message means identical plaintexts produce different ciphertexts. The nonce is stored alongside the ciphertext (it is not secret).
- **SSE (not WebSockets) for real-time delivery** — messaging here is one-directional server→client push, which is exactly what SSE provides over plain HTTP, with auto-reconnect built into the browser `EventSource`. WebSockets add bidirectional complexity we don't need at this stage.
- **JWT (stateless) for sessions** — the server verifies a signed token instead of looking up a session store on every request. Trade-off: tokens can't be revoked before their 24h expiry without extra infrastructure (a denylist).
- **Key management** — both the AES key (`secret.key`) and the JWT secret (`jwt_secret.key`) are loaded from disk (or, for the JWT secret, the `JWT_SECRET` env var) and are **git-ignored**. Because they persist across restarts, **stored messages remain decryptable and issued tokens stay valid after a restart** — the common failure mode of generating a fresh key at startup is avoided. In production these belong in a secrets manager.

**What a production version would still need:** rate limiting on `POST /login` (and "always hash" even for unknown users to close the timing/enumeration side-channel), per-recipient filtering on the SSE stream, CORS configuration for a hosted browser client, and database migrations (Alembic).

## Testing

```bash
pytest tests/ -v
```

23 tests covering:
- Authentication (register, login, token validation)
- Encryption (round-trip, nonce uniqueness, tamper detection, DB storage)
- Messaging (send, retrieve, message privacy)
- SSE (connection, auth rejection, broadcast delivery, multi-client broadcast)

## How Real-Time Messaging Works

```
User A — POST /messages
    ├─ Encrypt content
    ├─ Save to DB
    └─ broadcaster.publish()
            ├─→ User B's /stream queue
            ├─→ User C's /stream queue
            └─→ User D's /stream queue
```

Each connected `/stream` client has its own async queue. The `Broadcaster` enqueues every published message to all active queues. Disconnections are handled gracefully.

## Emotion Camera (Web UI)

The web UI includes a 📷 button that opens a webcam modal. It captures frames once per second and sends them to an emotion detection microservice at `http://localhost:5001/analyze`. The service returns an emotion label and emoji, which can be inserted directly into the message input.

The main messenger server does not need to run the emotion service — it is an optional companion.

## License

MIT
