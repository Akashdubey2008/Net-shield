import sqlite3
import os
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get('NETSHIELD_DB_PATH', os.path.join(os.path.dirname(__file__), 'netshield.db'))

DEFAULT_LINKS = [
    {"a": "CC", "b": "A", "weight": 1.0, "active": 1},
    {"a": "CC", "b": "B", "weight": 1.2, "active": 1},
    {"a": "CC", "b": "C", "weight": 1.0, "active": 1},
    {"a": "CC", "b": "D", "weight": 1.4, "active": 1},
    {"a": "CC", "b": "E", "weight": 1.3, "active": 1},
    {"a": "A", "b": "B", "weight": 1.0, "active": 1},
    {"a": "B", "b": "C", "weight": 1.0, "active": 1},
    {"a": "A", "b": "D", "weight": 1.1, "active": 1},
    {"a": "D", "b": "E", "weight": 1.0, "active": 1},
    {"a": "C", "b": "E", "weight": 1.1, "active": 1},
]

DEFAULT_USERS = [
    {
        "username": "commander",
        "password": "password123",
        "full_name": "Capt. Sarah Vance",
        "callsign": "VANGUARD-1",
        "role": "Command Officer",
        "unit_id": "CC",
        "clearance_level": "Level 3 - Top Secret"
    },
    {
        "username": "alpha_lead",
        "password": "password123",
        "full_name": "Lt. Marcus Cole",
        "callsign": "SPEARHEAD-ALPHA",
        "role": "Communications Officer",
        "unit_id": "A",
        "clearance_level": "Level 2 - Secret"
    },
    {
        "username": "bravo_tech",
        "password": "password123",
        "full_name": "Spec. Elena Rostova",
        "callsign": "SENTRY-BRAVO",
        "role": "Field Specialist",
        "unit_id": "B",
        "clearance_level": "Level 1 - Confidential"
    }
]

def get_db(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=None):
    conn = get_db(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        callsign TEXT NOT NULL,
        role TEXT NOT NULL,
        unit_id TEXT NOT NULL,
        clearance_level TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        a TEXT NOT NULL,
        b TEXT NOT NULL,
        weight REAL NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        UNIQUE(a, b)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT NOT NULL,
        sender_id INTEGER,
        sender_username TEXT NOT NULL,
        sender_name TEXT NOT NULL,
        sender_callsign TEXT NOT NULL,
        sender_role TEXT NOT NULL,
        sender_unit TEXT NOT NULL,
        source TEXT NOT NULL,
        target TEXT NOT NULL,
        message TEXT NOT NULL,
        priority TEXT NOT NULL,
        category TEXT NOT NULL,
        path_json TEXT NOT NULL,
        status TEXT NOT NULL,
        delay REAL NOT NULL,
        signature TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT NOT NULL,
        event_type TEXT NOT NULL,
        text TEXT NOT NULL,
        actor TEXT NOT NULL DEFAULT 'SYSTEM',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Seed default links if table is empty
    cursor.execute('SELECT COUNT(*) FROM links')
    if cursor.fetchone()[0] == 0:
        for link in DEFAULT_LINKS:
            cursor.execute(
                'INSERT INTO links (a, b, weight, active) VALUES (?, ?, ?, ?)',
                (link['a'], link['b'], link['weight'], link['active'])
            )

    # Seed default users if empty
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        for u in DEFAULT_USERS:
            pw_hash = generate_password_hash(u['password'])
            cursor.execute('''
            INSERT INTO users (username, password_hash, full_name, callsign, role, unit_id, clearance_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (u['username'], pw_hash, u['full_name'], u['callsign'], u['role'], u['unit_id'], u['clearance_level']))

    # Seed initial event if empty
    cursor.execute('SELECT COUNT(*) FROM events')
    if cursor.fetchone()[0] == 0:
        now_time = datetime.now().strftime('%H:%M:%S')
        cursor.execute('''
        INSERT INTO events (time, event_type, text, actor)
        VALUES (?, 'good', 'Tactical command network initialized. Security clearance active.', 'SYSTEM')
        ''', (now_time,))

    conn.commit()
    conn.close()

# ----------------- User Management ----------------- #

def get_user_by_id(user_id, db_path=None):
    conn = get_db(db_path)
    user = conn.execute('SELECT id, username, full_name, callsign, role, unit_id, clearance_level, created_at FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_username(username, db_path=None):
    conn = get_db(db_path)
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(username, password, full_name, callsign, role, unit_id, clearance_level, db_path=None):
    conn = get_db(db_path)
    pw_hash = generate_password_hash(password)
    try:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO users (username, password_hash, full_name, callsign, role, unit_id, clearance_level)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username.strip().lower(), pw_hash, full_name.strip(), callsign.strip().upper(), role, unit_id, clearance_level))
        user_id = cursor.lastrowid
        conn.commit()
        return get_user_by_id(user_id, db_path)
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

# ----------------- Link Management ----------------- #

def get_links(db_path=None):
    conn = get_db(db_path)
    rows = conn.execute('SELECT a, b, weight, active FROM links ORDER BY id ASC').fetchall()
    conn.close()
    return [{"a": r["a"], "b": r["b"], "weight": r["weight"], "active": bool(r["active"])} for r in rows]

def set_link_state(a, b, active, db_path=None):
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE links SET active = ? WHERE (a = ? AND b = ?) OR (a = ? AND b = ?)
    ''', (1 if active else 0, a, b, b, a))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def toggle_link_state(a, b, db_path=None):
    conn = get_db(db_path)
    cursor = conn.cursor()
    row = cursor.execute('SELECT active FROM links WHERE (a = ? AND b = ?) OR (a = ? AND b = ?)', (a, b, b, a)).fetchone()
    if not row:
        conn.close()
        return None
    new_active = 0 if row["active"] else 1
    cursor.execute('UPDATE links SET active = ? WHERE (a = ? AND b = ?) OR (a = ? AND b = ?)', (new_active, a, b, b, a))
    conn.commit()
    conn.close()
    return bool(new_active)

def reset_all_links(db_path=None):
    conn = get_db(db_path)
    conn.execute('UPDATE links SET active = 1')
    conn.commit()
    conn.close()

# ----------------- Messages ----------------- #

def add_message(sender, source, target, message, priority, category, path, status, delay, signature, db_path=None):
    conn = get_db(db_path)
    now_time = datetime.now().strftime('%H:%M:%S')
    path_json = json.dumps(path)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO messages (time, sender_id, sender_username, sender_name, sender_callsign, sender_role, sender_unit, source, target, message, priority, category, path_json, status, delay, signature)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        now_time,
        sender.get('id'),
        sender.get('username', 'UNKNOWN'),
        sender.get('full_name', 'Unknown Operator'),
        sender.get('callsign', 'GHOST'),
        sender.get('role', 'Operator'),
        sender.get('unit_id', 'UNKNOWN'),
        source,
        target,
        message,
        priority,
        category,
        path_json,
        status,
        delay,
        signature
    ))
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        "id": msg_id,
        "time": now_time,
        "sender": {
            "id": sender.get('id'),
            "username": sender.get('username'),
            "name": sender.get('full_name'),
            "callsign": sender.get('callsign'),
            "role": sender.get('role'),
            "unit": sender.get('unit_id')
        },
        "source": source,
        "target": target,
        "message": message,
        "priority": priority,
        "category": category,
        "path": path,
        "status": status,
        "delay": delay,
        "signature": signature,
        "verified": True
    }

def get_messages(limit=50, db_path=None):
    conn = get_db(db_path)
    rows = conn.execute('''
    SELECT id, time, sender_id, sender_username, sender_name, sender_callsign, sender_role, sender_unit,
           source, target, message, priority, category, path_json, status, delay, signature
    FROM messages ORDER BY id DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "time": r["time"],
            "sender": {
                "id": r["sender_id"],
                "username": r["sender_username"],
                "name": r["sender_name"],
                "callsign": r["sender_callsign"],
                "role": r["sender_role"],
                "unit": r["sender_unit"]
            },
            "source": r["source"],
            "target": r["target"],
            "message": r["message"],
            "priority": r["priority"],
            "category": r["category"],
            "path": json.loads(r["path_json"]) if r["path_json"] else [],
            "status": r["status"],
            "delay": r["delay"],
            "signature": r["signature"],
            "verified": True
        })
    return result

# ----------------- Events ----------------- #

def add_event(event_type, text, actor='SYSTEM', db_path=None):
    conn = get_db(db_path)
    now_time = datetime.now().strftime('%H:%M:%S')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO events (time, event_type, text, actor)
    VALUES (?, ?, ?, ?)
    ''', (now_time, event_type, text, actor))
    conn.commit()
    conn.close()

def get_events(limit=15, db_path=None):
    conn = get_db(db_path)
    rows = conn.execute('SELECT time, event_type, text, actor FROM events ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [{"time": r["time"], "type": r["event_type"], "text": r["text"], "actor": r["actor"]} for r in rows]

# ----------------- Stats & Aggregation ----------------- #

def get_stats(nodes_count, db_path=None):
    conn = get_db(db_path)
    links = conn.execute('SELECT active FROM links').fetchall()
    total_links = len(links)
    active_links = sum(1 for r in links if r["active"])
    failed_links = total_links - active_links
    uptime = round(active_links / total_links * 100) if total_links else 100

    msg_counts = conn.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) as delivered,
        SUM(CASE WHEN status = 'No route' THEN 1 ELSE 0 END) as failed_msgs,
        AVG(delay) as avg_delay
    FROM messages
    ''').fetchone()
    conn.close()

    total_msgs = msg_counts["total"] or 0
    delivered = msg_counts["delivered"] or 0
    failed_msgs = msg_counts["failed_msgs"] or 0
    avg_delay = round(msg_counts["avg_delay"], 1) if msg_counts["avg_delay"] is not None else 0.0

    return {
        "units": nodes_count,
        "active": active_links,
        "failed": failed_links,
        "uptime": uptime,
        "messages": total_msgs,
        "delivered": delivered,
        "failedMessages": failed_msgs,
        "avgDelay": avg_delay
    }
