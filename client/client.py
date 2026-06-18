"""
client.py — Terminal CLI client for Secure Messenger.

This is a real-time messaging client that runs in your terminal.
It connects to the server via HTTP/SSE and lets you send and receive messages.

HOW TO RUN:
  python -m client.client

FEATURES:
  - Register a new account or login to existing one
  - View message history
  - Send messages to other users
  - Receive messages in real-time via SSE (no polling!)
  - Type messages interactively

EXAMPLE:
  =========================
    Secure Messenger CLI
  =========================
  1) Register
  2) Login
  Choose (1/2): 2
  
  Username: alice
  Password: ••••••••
  
  Welcome, alice!
  Type 'quit' to exit
  
    [bob → alice]: hey, are you there?
    [bob → alice]: let's sync tomorrow
    > hi bob!
"""

import httpx
import json
import threading
import time
from getpass import getpass
from typing import Optional


BASE_URL = "http://localhost:8000"
token: Optional[str] = None
username: Optional[str] = None


def prompt_auth() -> tuple[str, str]:
    """Prompt user to register or login. Returns (username, token)."""
    global token, username
    
    print("\n" + "=" * 40)
    print("  Secure Messenger CLI")
    print("=" * 40)
    
    choice = input("\n1) Register\n2) Login\nChoose (1/2): ").strip()
    
    if choice == "1":
        return register_user()
    elif choice == "2":
        return login_user()
    else:
        print("Invalid choice. Try again.")
        return prompt_auth()


def register_user() -> tuple[str, str]:
    """Register a new account."""
    global token, username
    
    print("\n--- Register ---")
    username = input("Choose a username: ").strip()
    password = getpass("Choose a password (min 6 chars): ")
    
    try:
        response = httpx.post(
            f"{BASE_URL}/register",
            json={"username": username, "password": password}
        )
        
        if response.status_code == 201:
            print(f"✓ Registered! Now logging in...")
            # Auto-login after registration
            return login_with_credentials(username, password)
        else:
            print(f"✗ Registration failed: {response.json()}")
            return prompt_auth()
    except Exception as e:
        print(f"✗ Error: {e}")
        return prompt_auth()


def login_user() -> tuple[str, str]:
    """Login to existing account."""
    print("\n--- Login ---")
    username = input("Username: ").strip()
    password = getpass("Password: ")
    
    return login_with_credentials(username, password)


def login_with_credentials(user: str, password: str) -> tuple[str, str]:
    """Attempt login with given credentials."""
    global token, username
    
    try:
        response = httpx.post(
            f"{BASE_URL}/login",
            json={"username": user, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data["access_token"]
            username = user
            print(f"\n✓ Welcome, {username}!")
            return user, token
        else:
            print(f"✗ Login failed: {response.json()}")
            return prompt_auth()
    except Exception as e:
        print(f"✗ Error: {e}")
        return prompt_auth()


def get_headers() -> dict:
    """Return HTTP headers with auth token."""
    return {"Authorization": f"Bearer {token}"}


def display_message_history():
    """Fetch and display recent messages."""
    try:
        response = httpx.get(
            f"{BASE_URL}/messages",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            messages = response.json()
            if messages:
                print("\n--- Recent Messages ---")
                for msg in messages[-5:]:  # Show last 5 messages
                    sender = msg["sender"]
                    recipient = msg["recipient"]
                    content = msg["content"]
                    created = msg["created_at"]
                    
                    # Show who sent to whom
                    from_to = f"{sender} → {recipient}"
                    if sender == username:
                        print(f"  [you → {recipient}]: {content}")
                    else:
                        print(f"  [{sender} → you]: {content}")
            else:
                print("\n(No messages yet)")
    except Exception as e:
        print(f"Error fetching messages: {e}")


def listen_for_messages():
    """
    Background thread that listens to SSE stream.
    When messages arrive, print them to the terminal.
    """
    global token, username
    
    while True:
        try:
            with httpx.stream(
                "GET",
                f"{BASE_URL}/stream",
                headers=get_headers(),
                timeout=None  # Don't timeout — keep connection open forever
            ) as response:
                if response.status_code != 200:
                    print(f"\n✗ Stream failed: {response.status_code}")
                    time.sleep(2)
                    continue
                
                # Read SSE stream line by line
                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    if line.startswith("data: "):
                        # Parse the JSON message
                        try:
                            data = json.loads(line[6:])  # Skip "data: " prefix
                            sender = data.get("sender")
                            recipient = data.get("recipient")
                            content = data.get("content")
                            
                            # Only show messages where we're the recipient
                            if recipient == username:
                                print(f"\n  [{sender} → you]: {content}")
                                print(f"  > ", end="", flush=True)
                        except json.JSONDecodeError:
                            pass
        except httpx.NetworkError:
            print("\n✗ Connection lost. Reconnecting in 2 seconds...")
            time.sleep(2)
        except Exception as e:
            print(f"\n✗ Stream error: {e}")
            time.sleep(2)


def send_message(recipient: str, content: str):
    """Send a message to another user."""
    try:
        response = httpx.post(
            f"{BASE_URL}/messages",
            json={"recipient": recipient, "content": content},
            headers=get_headers()
        )
        
        if response.status_code == 201:
            return True
        else:
            print(f"✗ Failed to send: {response.json()}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main_loop():
    """Main interactive loop — read user input and send messages."""
    global username
    
    print(f"\nType messages in format: <username> <message>")
    print("Or just type the message and you'll be prompted for the recipient.")
    print("Type 'history' to see recent messages.")
    print("Type 'quit' to exit.\n")
    
    display_message_history()
    
    while True:
        try:
            user_input = input(f"  > ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "quit":
                print("Goodbye!")
                break
            
            if user_input.lower() == "history":
                display_message_history()
                continue
            
            # Parse input: "<username> <message>" or just "<message>"
            parts = user_input.split(" ", 1)
            
            if len(parts) == 2:
                recipient, content = parts
            else:
                recipient = input("  Recipient: ").strip()
                content = user_input
            
            if send_message(recipient, content):
                print(f"  ✓ Sent to {recipient}")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point."""
    global token, username
    
    print("\n🔒 Secure Messenger v2.0 (Stage 2 with real-time messaging)")
    
    # Step 1: Authenticate
    username, token = prompt_auth()
    
    # Step 2: Start background thread to listen for incoming messages
    listener_thread = threading.Thread(target=listen_for_messages, daemon=True)
    listener_thread.start()
    
    # Give the listener a moment to connect
    time.sleep(0.5)
    
    # Step 3: Main loop — read user input and send messages
    main_loop()


if __name__ == "__main__":
    main()
