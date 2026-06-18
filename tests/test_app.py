"""
test_app.py — Stage 1 & Stage 2 test suite.

INCLUDES:
  - Stage 1: Authentication, encryption, messaging REST API
  - Stage 2: Server-Sent Events (SSE) real-time messaging

HOW TO RUN:
  pytest tests/ -v

HOW TESTS WORK HERE:
  We use FastAPI's TestClient — it sends real HTTP requests to your app
  without needing to start a server. Each test gets a fresh, empty
  database so tests never interfere with each other.

  The test database is a separate file (test_messenger.db) and is
  wiped clean before every single test.
"""

import pytest
import json
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.main import app
from server.models import Base, get_db
from server.crypto import encrypt, decrypt
from server.broadcaster import broadcaster


# ---------------------------------------------------------------------------
# Test database setup — uses a separate file, wiped before each test
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///./test_messenger.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    
    # Clear broadcaster subscriptions after each test
    broadcaster.subscriptions.clear()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register_and_login(client, username="alice", password="secret123") -> str:
    """Register a user and return their JWT token."""
    client.post("/register", json={"username": username, "password": password})
    response = client.post("/login", json={"username": username, "password": password})
    return response.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# 1. Authentication tests
# ===========================================================================

class TestAuthentication:

    def test_register_success(self, client):
        response = client.post("/register", json={"username": "alice", "password": "secret123"})
        assert response.status_code == 201

    def test_register_duplicate_username(self, client):
        client.post("/register", json={"username": "alice", "password": "secret123"})
        response = client.post("/register", json={"username": "alice", "password": "other-password"})
        assert response.status_code == 400

    def test_register_password_too_short(self, client):
        response = client.post("/register", json={"username": "alice", "password": "abc"})
        assert response.status_code == 422   # Pydantic rejects it before your code runs

    def test_login_success(self, client):
        client.post("/register", json={"username": "alice", "password": "secret123"})
        response = client.post("/login", json={"username": "alice", "password": "secret123"})
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_wrong_password(self, client):
        client.post("/register", json={"username": "alice", "password": "secret123"})
        response = client.post("/login", json={"username": "alice", "password": "wrongpassword"})
        assert response.status_code == 401

    def test_login_unknown_user(self, client):
        response = client.post("/login", json={"username": "ghost", "password": "secret123"})
        assert response.status_code == 401

    def test_messages_require_token(self, client):
        response = client.get("/messages")
        assert response.status_code in (401, 403)

    def test_messages_reject_bad_token(self, client):
        response = client.get("/messages", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 401

    def test_messages_accept_valid_token(self, client):
        token = register_and_login(client)
        response = client.get("/messages", headers=auth(token))
        assert response.status_code == 200

    def test_stream_requires_token(self, client):
        """Verify that /stream rejects requests without valid token."""
        response = client.get("/stream")
        assert response.status_code in (401, 403)

    def test_stream_reject_bad_token(self, client):
        """Verify that /stream rejects requests with bad token."""
        response = client.get("/stream", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 401


# ===========================================================================
# 2. Encryption tests
# ===========================================================================

class TestEncryption:

    def test_encrypt_is_not_plain_text(self):
        assert encrypt("hello world") != "hello world"

    def test_decrypt_round_trip(self):
        original = "this is a secret message"
        assert decrypt(encrypt(original)) == original

    def test_same_message_encrypts_differently_each_time(self):
        # fresh nonce every call → different ciphertext
        assert encrypt("hello") != encrypt("hello")

    def test_tampered_ciphertext_raises(self):
        blob = encrypt("original")
        tampered = blob[:-4] + "XXXX"
        with pytest.raises(Exception):
            decrypt(tampered)

    def test_messages_are_stored_encrypted(self, client):
        """Verify that messages are stored encrypted in the database."""
        from server.models import Message
        token = register_and_login(client)
        register_and_login(client, "bob", "secret456")
        
        # Send a message
        response = client.post(
            "/messages",
            json={"content": "secret message", "recipient": "bob"},
            headers=auth(token)
        )
        assert response.status_code == 201
        
        # Query the DB directly
        db = TestingSession()
        row = db.query(Message).first()
        db.close()
        
        # Verify: ciphertext is not plain text
        assert row.ciphertext != "secret message"
        
        # Verify: can decrypt it back to original
        assert decrypt(row.ciphertext) == "secret message"


# ===========================================================================
# 3. Messaging tests
# ===========================================================================

class TestMessaging:

    def test_send_message_success(self, client):
        alice_token = register_and_login(client, "alice", "secret123")
        register_and_login(client, "bob", "secret456")

        response = client.post(
            "/messages",
            json={"content": "hello bob", "recipient": "bob"},
            headers=auth(alice_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "hello bob"   # returned decrypted
        assert data["sender"] == "alice"
        assert data["recipient"] == "bob"

    def test_get_messages_returns_decrypted(self, client):
        alice_token = register_and_login(client, "alice", "secret123")
        register_and_login(client, "bob", "secret456")

        client.post("/messages", json={"content": "hi bob", "recipient": "bob"}, headers=auth(alice_token))

        response = client.get("/messages", headers=auth(alice_token))
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) >= 1
        assert messages[0]["content"] == "hi bob"   # must be decrypted, not ciphertext

    def test_user_sees_only_their_messages(self, client):
        """Verify that users only see messages where they're sender or recipient."""
        alice_token = register_and_login(client, "alice", "secret123")
        bob_token   = register_and_login(client, "bob",   "secret456")
        register_and_login(client, "charlie", "secret789")

        # alice → bob
        client.post("/messages", json={"content": "msg1", "recipient": "bob"}, headers=auth(alice_token))
        
        # bob → alice
        client.post("/messages", json={"content": "msg2", "recipient": "alice"}, headers=auth(bob_token))
        
        # charlie → bob (alice should NOT see this)
        charlie_token = register_and_login(client, "charlie", "secret789")
        client.post("/messages", json={"content": "msg3", "recipient": "bob"}, headers=auth(charlie_token))

        # Alice should see only messages where she's sender or recipient (msg1 and msg2)
        response = client.get("/messages", headers=auth(alice_token))
        alice_messages = response.json()
        assert len(alice_messages) == 2
        contents = [msg["content"] for msg in alice_messages]
        assert "msg1" in contents
        assert "msg2" in contents
        assert "msg3" not in contents


# ===========================================================================
# 4. Server-Sent Events (SSE) tests
# ===========================================================================

class TestSSE:

    def test_stream_connection_success(self, client):
        """Verify that /stream accepts valid auth and opens connection."""
        token = register_and_login(client)
        with client.stream("GET", "/stream", headers=auth(token)) as response:
            assert response.status_code == 200

    def test_stream_requires_valid_auth(self, client):
        """Verify that /stream rejects invalid tokens."""
        response = client.get("/stream", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401

    def test_sse_receives_broadcast(self, client):
        """
        Verify that when a message is sent, connected SSE clients receive it.
        
        Test flow:
          1. Alice and Bob register
          2. Alice connects to /stream (SSE)
          3. Bob sends a message to Alice
          4. Alice receives it via SSE
        """
        alice_token = register_and_login(client, "alice", "secret123")
        bob_token = register_and_login(client, "bob", "secret456")

        # Alice connects to SSE stream
        with client.stream("GET", "/stream", headers=auth(alice_token)) as response:
            assert response.status_code == 200
            
            # Bob sends a message to Alice
            send_response = client.post(
                "/messages",
                json={"content": "hello alice", "recipient": "alice"},
                headers=auth(bob_token)
            )
            assert send_response.status_code == 201
            
            # Alice should receive the message on the SSE stream
            lines = []
            for line in response.iter_lines():
                lines.append(line)
                if len(lines) >= 1 and "bob" in line:
                    break
            
            # Verify we received data
            assert len(lines) > 0
            # Find the data line
            data_line = next((l for l in lines if l.startswith("data:")), None)
            assert data_line is not None
            
            # Parse the JSON message
            message_json = data_line[6:].strip()  # Remove "data: "
            message = json.loads(message_json)
            assert message["sender"] == "bob"
            assert message["content"] == "hello alice"

    def test_multiple_clients_receive_broadcast(self, client):
        """
        Verify that multiple connected clients all receive broadcasts.
        
        Test flow:
          1. Alice, Bob, Charlie register
          2. Alice and Bob connect to /stream
          3. Charlie sends a message
          4. Both Alice and Bob receive it via SSE
        """
        alice_token = register_and_login(client, "alice", "secret123")
        bob_token = register_and_login(client, "bob", "secret456")
        charlie_token = register_and_login(client, "charlie", "secret789")

        # Alice connects to SSE stream
        alice_stream = client.stream("GET", "/stream", headers=auth(alice_token))
        alice_response = alice_stream.__enter__()
        
        # Bob connects to SSE stream
        bob_stream = client.stream("GET", "/stream", headers=auth(bob_token))
        bob_response = bob_stream.__enter__()
        
        try:
            assert alice_response.status_code == 200
            assert bob_response.status_code == 200
            
            # Charlie sends a message to Alice
            client.post(
                "/messages",
                json={"content": "broadcast test", "recipient": "alice"},
                headers=auth(charlie_token)
            )
            
            # Both should receive via their streams
            alice_lines = []
            bob_lines = []
            
            for line in alice_response.iter_lines():
                alice_lines.append(line)
                if "broadcast test" in line:
                    break
            
            for line in bob_response.iter_lines():
                bob_lines.append(line)
                if "broadcast test" in line:
                    break
            
            # Both should have received the message
            assert len(alice_lines) > 0
            assert len(bob_lines) > 0
            
        finally:
            alice_stream.__exit__(None, None, None)
            bob_stream.__exit__(None, None, None)

