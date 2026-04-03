# P2P Messenger

A fully decentralized, end-to-end encrypted peer-to-peer messaging application.

## Features

- **End-to-End Encryption**: All messages are encrypted using AES-256-GCM with ECDH key exchange
- **No Central Servers**: Fully decentralized - connects directly between peers
- **Local Network Discovery**: Automatically discovers peers on your local network via UDP broadcast
- **Manual Contact Addition**: Add contacts by IP address/hostname for internet connections
- **File Transfer**: Send files with chunked transfer and ACK confirmation
- **Typing Indicators**: See when the other person is typing
- **Read Receipts**: Know when your messages have been read
- **Certificate-Based Identity**: Each user has a unique cryptographic identity

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python main.py
```

## Usage

### First Time Setup
1. Launch the application
2. Enter a username to create your account
3. Your unique User ID and fingerprint will be generated

### Adding Contacts

#### Local Network (Automatic)
- Contacts on the same local network will be discovered automatically via UDP broadcast

#### Internet/Manual
1. Click "+ Add Contact"
2. Enter the contact's name, IP address, and port (default: 37021)
3. The contact must be online and have port forwarding set up if behind NAT

### Sending Messages
1. Double-click a contact to open the chat
2. Type your message and press Enter or click Send
3. Files can be attached using the paperclip button

## Technical Details

### Security
- **ECDH Key Exchange**: SECP256R1 curve for session key derivation
- **AES-256-GCM**: Authenticated encryption for all messages
- **HMAC-SHA256**: Message authentication codes
- **RSA-3072**: Digital signatures for certificates

### Network Protocol
- **UDP Port 37020**: Peer discovery via broadcast
- **TCP Port 37021**: Encrypted message transport

### File Transfer
- Files are split into 4KB chunks
- Each chunk requires ACK confirmation
- Automatic retry on failed chunks (3 attempts)

## Project Structure

```
p2p_messenger/
├── main.py              # Application entry point
├── gui/                 # Graphical user interface
│   ├── app.py          # Main application class
│   ├── home_frame.py   # Contacts list view
│   ├── chat_frame.py   # Chat window
│   ├── profile_frame.py # User profile/settings
│   └── register_frame.py # Registration screen
├── core/               # Core functionality
│   └── database_helper.py # SQLite database access
├── models/             # Data models
│   ├── user_profile.py # User identity
│   ├── contact.py      # Contact information
│   └── message.py      # Message structure
├── providers/          # Business logic
│   ├── contact_provider.py # Contact management
│   └── chat_provider.py    # Chat operations
├── security/           # Cryptography
│   ├── crypto_utils.py # Encryption/signing
│   └── cert_store.py   # Certificate storage
├── transports/         # Network transports
│   ├── base_transport.py     # Abstract base
│   └── secure_tcp_transport.py # Encrypted TCP
├── services/           # Background services
│   └── udp_discovery.py # Peer discovery
├── network/            # Network utilities
│   └── interface_manager.py # Interface detection
└── utils/              # Utilities
    └── constants.py    # Configuration constants
```

## Requirements

- Python 3.8+
- tkinter (usually included with Python)
- cryptography >= 41.0.0
- netifaces >= 0.11.0

## License

MIT License - Feel free to use and modify as needed.

## Security Notice

This is a peer-to-peer application. For connections over the internet:
- You may need to configure port forwarding on your router
- Consider using a VPN for additional privacy
- Always verify contact fingerprints before sharing sensitive information
