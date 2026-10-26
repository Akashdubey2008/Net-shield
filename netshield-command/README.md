# NetShield Command — Tactical Coordination & Identity System

A browser-based, network-centric command and communication simulation. NetShield Command features secure user authentication, role-based access control (RBAC), operator identity verification, SHA-256 cryptographic message signatures, persistent SQLite storage, dynamic Dijkstra shortest-path routing, link failure simulations, real-time packet flow animations, and rule-based AI situation assessments.

> **Safety / scope:** This is an educational simulation. It does not connect to real-world military or defense networks, use classified operational data, or implement real military hardware protocols.

---

## Key Features & Enhancements

1. **User Authentication & Tiered Role Powers (RBAC)**
   - Secure operator login and registration with password hashing (`werkzeug.security`).
   - Session-based protection for all operational API routes.
   - Verified operator attribution: every transmission is cryptographically signed with a SHA-256 signature (`SIG-XXXXXXXXXXXX`) derived from operator credentials, source, target, timestamp, and payload.
   - **Role Hierarchy & Communication Power Matrix**:
     | Operational Power | **Command Officer** (Level 3) | **Communications Officer** (Level 2) | **Field Specialist** (Level 1) |
     |---|:---:|:---:|:---:|
     | **Transmission Origin** | **Any Station** (`CC`, `A`, `B`, `C`, `D`, `E`) | **Assigned Station** or **`CC`** | **Strictly Assigned Station Only** |
     | **Destination Range** | **All Stations** (Full Mesh) | **All Stations** (Full Mesh) | **Command Center (`CC`) & Direct Radio Neighbors** |
     | **Priority Levels** | **Urgent Flash Override**, High, Normal, Low | **High**, Normal, Low | **Normal**, **Low** only |
     | **Fleet Broadcast** | **Authorized** (Flash Override to all 5 units) | **Restricted** (Forbidden) | **Restricted** (Forbidden) |
     | **Link Toggles & Outages** | **Authorized** (Simulate failures & restore) | **Read-Only Monitoring** | **Read-Only Monitoring** |
     | **Restore All Links** | **Authorized** | **Restricted** (Forbidden) | **Restricted** (Forbidden) |
     | **AI Situation Summary** | **Authorized** (Generate assessment) | **Authorized** (Generate assessment) | **Read-Only View** |
     | **Log Debrief Export** | **Authorized** (CSV & JSON) | **Authorized** (CSV & JSON) | **Restricted** (Forbidden) |

2. **Persistent Tactical Database (SQLite)**
   - All user accounts, message transmissions, link states, and chronological audit logs persist across server restarts in `netshield.db`.
   - Automatic database schema initialization on startup.

3. **Dynamic Dijkstra Shortest-Path Routing**
   - Automatically recalculates optimal paths across active weighted links.
   - Immediate detection of network partitions ("No route").
   - Animated SVG packet flow: Visualizes packets traversing calculated hops in real time.

4. **Operational Enhancements**
   - **Incoming Transmission Pop-Up Alert:** When any unit sends a message to your station (`target === unit_id`), a high-priority cyber-tactical pop-up alert triggers instantly with sound effects, displaying originating station, operator callsign, priority, decrypted message content, Dijkstra route, and digital signature. Includes a 1-click `📥 Test Inbound Alert` button.
   - **Priority Broadcast:** Command Officers can issue simultaneous flash alerts to all units.
   - **Audit & Security Event Log:** Chronological system events with actor attribution.
   - **Log Search & Filters:** Filter messages by priority (Urgent, High, Normal, Low), delivery status, or search by callsign/keyword.
   - **Debrief Export:** Export message logs to CSV or JSON with one click.
   - **Tactical Audio FX:** Synthesized feedback using the Web Audio API (with mute/unmute toggle).

---

## Default Demo Personnel (Pre-Seeded)

For demonstration and evaluation, three pre-configured operator accounts are provisioned in the database. Operators must manually enter their credentials on the Sign In portal or register a new authorized operator account:

| Operator | Username | Password | Callsign | Unit | Clearance |
|---|---|---|---|---|---|
| **Capt. Sarah Vance** | `commander` | `password123` | `VANGUARD-1` | Command Center (`CC`) | Level 3 - Top Secret |
| **Lt. Marcus Cole** | `alpha_lead` | `password123` | `SPEARHEAD-ALPHA` | Alpha Unit (`A`) | Level 2 - Secret |
| **Spec. Elena Rostova** | `bravo_tech` | `password123` | `SENTRY-BRAVO` | Bravo Unit (`B`) | Level 1 - Confidential |

---

## Requirements
- Python 3.10 or newer
- Flask (3.0+)
- Modern browser

---

## How to Run

### Windows (PowerShell or Command Prompt)
```powershell
# 1. (Optional) Create and activate virtual environment
py -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
py -m pip install -r requirements.txt

# 3. Start the application
py app.py
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## Running Automated Tests

A comprehensive unit and integration test suite is included:

```powershell
python -m unittest tests/test_netshield.py
```

Tests verify:
- Authentication & session gating (401 enforcement).
- Operator registration and input validation.
- Cryptographic SHA-256 message signing & identity binding.
- Field specialist origin restriction enforcement.
- Dijkstra shortest-path rerouting around simulated outages.
- Priority broadcast to all operational nodes.
- AI situation summary generation.
- CSV and JSON log export formats.

---

## API Endpoints

### Authentication
- `POST /api/auth/login` — authenticate with username and password.
- `POST /api/auth/register` — register new operator credentials.
- `POST /api/auth/logout` — terminate authenticated session.
- `GET /api/auth/me` — retrieve active operator session details.

### Tactical Operations (Protected)
- `GET /api/state` — get network topology, link states, messages, audit events, and stats.
- `POST /api/message` — dispatch an identity-signed message and calculate Dijkstra path.
- `POST /api/broadcast` — issue priority flash transmission to all peripheral units.
- `POST /api/link` — toggle simulated link outage / restoration with operator attribution.
- `POST /api/reset` — restore all network links.
- `POST /api/summary` — generate rule-based situation summary.
- `GET /api/messages/export?format=csv|json` — download operational message logs.

---

## Project Structure

```text
netshield-command/
├── app.py                 # Flask app, Dijkstra pathfinding, auth gating, APIs
├── database.py            # SQLite persistence, schema, seed data, queries
├── netshield.db           # Persistent SQLite database (auto-generated)
├── requirements.txt       # Dependencies (Flask, Werkzeug)
├── README.md              # Documentation, credentials, architecture
├── templates/
│   └── index.html         # High-tech cyber command dashboard & auth portal
├── static/
│   ├── app.js             # Client state, audio FX, packet animation, filtering
│   └── style.css          # Tactical dark command HUD styling & animations
└── tests/
    └── test_netshield.py  # Comprehensive automated test suite (13 tests)
```
