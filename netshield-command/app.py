from flask import Flask, render_template, request, jsonify, session, Response
from functools import wraps
from datetime import datetime
import heapq
import re
import os
import io
import csv
import hashlib
from werkzeug.security import check_password_hash

import database

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'netshield-tactical-c2-secure-key-2026')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize database tables and seed accounts
database.init_db()

# Fictional nodes for the tactical simulation
NODES = [
    {"id": "CC", "name": "Command Center", "x": 50, "y": 48, "kind": "command"},
    {"id": "A", "name": "Alpha Unit", "x": 18, "y": 36, "kind": "unit"},
    {"id": "B", "name": "Bravo Unit", "x": 48, "y": 13, "kind": "unit"},
    {"id": "C", "name": "Charlie Unit", "x": 81, "y": 35, "kind": "unit"},
    {"id": "D", "name": "Delta Unit", "x": 29, "y": 79, "kind": "unit"},
    {"id": "E", "name": "Echo Unit", "x": 72, "y": 78, "kind": "unit"},
]

NODE_IDS = {n['id'] for n in NODES}

# Immediate direct connections (radio horizon) in the tactical mesh topology
ADJACENT_NODES = {
    'CC': {'A', 'B', 'C', 'D', 'E'},
    'A': {'CC', 'B', 'D'},
    'B': {'CC', 'A', 'C'},
    'C': {'CC', 'B', 'E'},
    'D': {'CC', 'A', 'E'},
    'E': {'CC', 'D', 'C'}
}

# Role-Based Access Control (RBAC) & Clearance Hierarchy
ROLE_PERMISSIONS = {
    'Command Officer': {
        'level': 3,
        'clearance': 'Level 3 - Top Secret',
        'badge_label': 'LEVEL 3: FULL FLEET COMMAND',
        'can_broadcast': True,
        'can_toggle_links': True,
        'can_reset_links': True,
        'can_generate_summary': True,
        'can_export_logs': True,
        'allowed_sources': ['CC', 'A', 'B', 'C', 'D', 'E'],
        'allowed_priorities': ['Urgent', 'High', 'Normal', 'Low'],
        'description': 'Full command authority: Transmit from any station, fleet-wide flash broadcasts, link failure toggling, AI situation reports, intelligence export.'
    },
    'Communications Officer': {
        'level': 2,
        'clearance': 'Level 2 - Secret',
        'badge_label': 'LEVEL 2: TACTICAL COMMS',
        'can_broadcast': False,
        'can_toggle_links': False,
        'can_reset_links': False,
        'can_generate_summary': True,
        'can_export_logs': True,
        'allowed_sources': ['ASSIGNED', 'CC'],
        'allowed_priorities': ['High', 'Normal', 'Low'],
        'description': 'Tactical communications lead: Multi-unit relay from assigned unit or Command Center, High/Normal/Low priorities, AI situation summary, intelligence export.'
    },
    'Field Specialist': {
        'level': 1,
        'clearance': 'Level 1 - Confidential',
        'badge_label': 'LEVEL 1: FIELD STATION',
        'can_broadcast': False,
        'can_toggle_links': False,
        'can_reset_links': False,
        'can_generate_summary': False,
        'can_export_logs': False,
        'allowed_sources': ['ASSIGNED'],
        'allowed_priorities': ['Normal', 'Low'],
        'description': 'Field tactical reporting: Strictly locked to assigned station, point-to-point reporting to Command Center or adjacent direct neighbors, Normal/Low priority.'
    }
}


# ----------------- Auth Helpers ----------------- #

def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    user = database.get_user_by_id(user_id)
    if user:
        perms = ROLE_PERMISSIONS.get(user['role'], ROLE_PERMISSIONS['Field Specialist'])
        user['permissions'] = perms
    return user


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required. Please log in with valid credentials.", "authenticated": False}), 401
        return f(*args, **kwargs)
    return decorated_function


def generate_message_signature(sender_username, sender_callsign, source, target, text, timestamp):
    """Generates a cryptographic SHA-256 identity verification signature."""
    payload = f"{sender_username}:{sender_callsign}:{source}:{target}:{timestamp}:{text}"
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    return f"SIG-{digest[:12].upper()}"


# ----------------- Routing & Classifier ----------------- #

def shortest_path(source, target, links=None):
    if links is None:
        links = database.get_links()
    graph = {n['id']: [] for n in NODES}
    for link in links:
        if link['active']:
            graph[link['a']].append((link['b'], link['weight']))
            graph[link['b']].append((link['a'], link['weight']))
    queue = [(0, source, [source])]
    best = {}
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node in best and best[node] <= cost:
            continue
        best[node] = cost
        if node == target:
            return path, round(cost, 2)
        for nxt, weight in graph[node]:
            if nxt not in path:
                heapq.heappush(queue, (cost + weight, nxt, path + [nxt]))
    return [], None


def classify(text):
    t = text.lower()
    rules = [
        ('Connectivity', ['link', 'connection', 'offline', 'network', 'signal', 'disconnect', 'packet', 'router']),
        ('Urgent assistance', ['help', 'urgent', 'support', 'emergency', 'injured', 'mayday', 'sos', 'danger']),
        ('Logistics', ['supply', 'vehicle', 'food', 'water', 'equipment', 'delivery', 'ammo', 'battery', 'fuel']),
        ('Status update', ['secure', 'ready', 'status', 'arrived', 'complete', 'patrol', 'nominal', 'confirmed']),
    ]
    for label, words in rules:
        if any(re.search(r'\b' + re.escape(word) + r'\b', t) for word in words):
            return label
    return 'General update'


def snapshot(current_user=None):
    links = database.get_links()
    messages = database.get_messages(limit=50)
    events = database.get_events(limit=15)
    stats = database.get_stats(len(NODES))
    return {
        "nodes": NODES,
        "links": links,
        "messages": messages,
        "events": events,
        "stats": stats,
        "currentUser": current_user
    }


# ----------------- Web Views ----------------- #

@app.route('/')
def index():
    return render_template('index.html')


# ----------------- Auth API Endpoints ----------------- #

@app.get('/api/auth/me')
def auth_me():
    user = get_current_user()
    if not user:
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "user": user})


@app.post('/api/auth/login')
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip().lower()
    password = str(data.get('password', ''))

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    user = database.get_user_by_username(username)
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "Invalid username or password. Check credentials or register."}), 401

    session['user_id'] = user['id']
    user_info = {
        "id": user['id'],
        "username": user['username'],
        "full_name": user['full_name'],
        "callsign": user['callsign'],
        "role": user['role'],
        "unit_id": user['unit_id'],
        "clearance_level": user['clearance_level']
    }

    database.add_event(
        'good',
        f"Operator '{user['full_name']}' [{user['callsign']}] authenticated successfully.",
        actor=user['callsign']
    )

    return jsonify({
        "message": "Authentication successful.",
        "user": user_info,
        "state": snapshot(user_info)
    })


@app.post('/api/auth/register')
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip().lower()
    password = str(data.get('password', ''))
    full_name = str(data.get('full_name', '')).strip()
    callsign = str(data.get('callsign', '')).strip().upper()
    role = str(data.get('role', 'Field Specialist')).strip()
    unit_id = str(data.get('unit_id', 'A')).strip().upper()

    # Validations
    if not re.match(r'^[a-z0-9_]{3,20}$', username):
        return jsonify({"error": "Username must be 3-20 alphanumeric characters or underscores."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long."}), 400
    if not full_name or len(full_name) > 50:
        return jsonify({"error": "Full name is required (max 50 chars)."}), 400
    if not callsign or len(callsign) > 20:
        return jsonify({"error": "Callsign is required (max 20 chars, e.g., VANGUARD-2)."}), 400

    valid_roles = {
        'Command Officer': 'Level 3 - Top Secret',
        'Communications Officer': 'Level 2 - Secret',
        'Field Specialist': 'Level 1 - Confidential'
    }
    if role not in valid_roles:
        role = 'Field Specialist'
    clearance_level = valid_roles[role]

    if unit_id not in NODE_IDS:
        unit_id = 'A'

    if database.get_user_by_username(username):
        return jsonify({"error": f"Username '{username}' is already registered."}), 409

    user = database.create_user(username, password, full_name, callsign, role, unit_id, clearance_level)
    if not user:
        return jsonify({"error": "Failed to create user account. Please try again."}), 500

    session['user_id'] = user['id']

    database.add_event(
        'good',
        f"New operator registered: '{user['full_name']}' [{user['callsign']}], assigned to {user['unit_id']}.",
        actor=user['callsign']
    )

    return jsonify({
        "message": "Registration successful. Welcome to NetShield Command.",
        "user": user,
        "state": snapshot(user)
    }), 201


@app.post('/api/auth/logout')
def logout():
    user = get_current_user()
    if user:
        database.add_event(
            'good',
            f"Operator '{user['full_name']}' [{user['callsign']}] signed out.",
            actor=user['callsign']
        )
    session.clear()
    return jsonify({"message": "Successfully signed out."})


# ----------------- Core Operations API ----------------- #

@app.get('/api/state')
@login_required
def state():
    user = get_current_user()
    return jsonify(snapshot(user))


@app.post('/api/message')
@login_required
def send_message():
    current_user = get_current_user()
    role = current_user.get('role', 'Field Specialist')
    perms = current_user.get('permissions', ROLE_PERMISSIONS['Field Specialist'])

    data = request.get_json(silent=True) or {}
    source = data.get('source')
    target = data.get('target')
    message = str(data.get('message', '')).strip()[:500]
    priority = data.get('priority', 'Normal')

    if source not in NODE_IDS or target not in NODE_IDS:
        return jsonify({"error": "Choose valid operational units."}), 400
    if source == target:
        return jsonify({"error": "Source and destination units must be different."}), 400
    if not message:
        return jsonify({"error": "Message content cannot be empty."}), 400

    # 1. Priority clearance validation
    if priority not in perms['allowed_priorities']:
        return jsonify({
            "error": f"Clearance Denied: Priority '{priority}' exceeds clearance level for {role}. Allowed priorities: {', '.join(perms['allowed_priorities'])}."
        }), 403

    # 2. Source origin clearance validation
    if role == 'Field Specialist':
        if source != current_user['unit_id']:
            return jsonify({
                "error": f"Clearance Denied: Field Specialist [{current_user['callsign']}] can only originate transmissions from assigned station ({current_user['unit_id']})."
            }), 403
    elif role == 'Communications Officer':
        if source != current_user['unit_id'] and source != 'CC':
            return jsonify({
                "error": f"Clearance Denied: Communications Officer can only originate from assigned station ({current_user['unit_id']}) or Command Center (CC)."
            }), 403

    # 3. Destination clearance validation for Field Specialist (Direct radio horizon: CC or adjacent nodes)
    if role == 'Field Specialist':
        allowed_targets = ADJACENT_NODES.get(source, set())
        if target not in allowed_targets:
            return jsonify({
                "error": f"Clearance Denied: Field Specialist direct transmission limited to Command Center or adjacent tactical units ({', '.join(sorted(allowed_targets))}). Relay via Command Center for long-range communications."
            }), 403

    path, cost = shortest_path(source, target)
    status = 'Delivered' if path else 'No route'
    delay = round((cost or 0) * 0.8 + 0.2, 1) if path else 0
    now_time = datetime.now().strftime('%H:%M:%S')

    signature = generate_message_signature(
        current_user['username'],
        current_user['callsign'],
        source,
        target,
        message,
        now_time
    )

    category = classify(message)

    record = database.add_message(
        sender=current_user,
        source=source,
        target=target,
        message=message,
        priority=priority,
        category=category,
        path=path,
        status=status,
        delay=delay,
        signature=signature
    )

    event_text = (
        f"[{current_user['callsign']}] Transmitted to {target} via {' → '.join(path)} ({status})"
        if path else
        f"[{current_user['callsign']}] Failed transmission {source} → {target} (No route)"
    )
    database.add_event(
        'good' if path else 'bad',
        event_text,
        actor=current_user['callsign']
    )

    return jsonify({"message": record, "state": snapshot(current_user)})


@app.post('/api/broadcast')
@login_required
def broadcast_alert():
    """Allows Command Officers (Level 3) to broadcast an urgent transmission to all peripheral units."""
    current_user = get_current_user()
    perms = current_user.get('permissions', {})
    if not perms.get('can_broadcast'):
        return jsonify({
            "error": f"Clearance Denied: Fleet Broadcast is exclusively reserved for Level 3 Command Officers. Current role: {current_user['role']}."
        }), 403

    data = request.get_json(silent=True) or {}
    message = str(data.get('message', '')).strip()[:500]
    if not message:
        message = "ALERT: NetShield tactical perimeter status update. All units acknowledge."

    source = "CC"
    destinations = [n['id'] for n in NODES if n['id'] != source]
    records = []

    for target in destinations:
        path, cost = shortest_path(source, target)
        status = 'Delivered' if path else 'No route'
        delay = round((cost or 0) * 0.8 + 0.2, 1) if path else 0
        now_time = datetime.now().strftime('%H:%M:%S')

        signature = generate_message_signature(
            current_user['username'],
            current_user['callsign'],
            source,
            target,
            message,
            now_time
        )

        rec = database.add_message(
            sender=current_user,
            source=source,
            target=target,
            message=message,
            priority="Urgent",
            category="Status update",
            path=path,
            status=status,
            delay=delay,
            signature=signature
        )
        records.append(rec)

    delivered_count = sum(1 for r in records if r['status'] == 'Delivered')
    database.add_event(
        'good',
        f"[{current_user['callsign']}] Priority Fleet Broadcast dispatched from Command Center to {len(destinations)} units ({delivered_count}/{len(destinations)} delivered).",
        actor=current_user['callsign']
    )

    return jsonify({
        "broadcast": records,
        "summary": f"Broadcast delivered to {delivered_count}/{len(destinations)} units.",
        "state": snapshot(current_user)
    })


@app.post('/api/message/simulate-incoming')
@login_required
def simulate_incoming_message():
    """Simulates an inbound transmission sent by an external operational unit to the current operator's unit."""
    current_user = get_current_user()
    target = current_user['unit_id']

    # Select an appropriate originating unit
    if target != 'CC':
        source = 'CC'
    else:
        source = 'A'

    simulated_senders = {
        'CC': {"id": 1, "username": "commander", "full_name": "Capt. Sarah Vance", "callsign": "VANGUARD-1", "role": "Command Officer", "unit_id": "CC"},
        'A': {"id": 2, "username": "alpha_lead", "full_name": "Lt. Marcus Cole", "callsign": "SPEARHEAD-ALPHA", "role": "Communications Officer", "unit_id": "A"},
        'B': {"id": 3, "username": "bravo_tech", "full_name": "Spec. Elena Rostova", "callsign": "SENTRY-BRAVO", "role": "Field Specialist", "unit_id": "B"},
        'C': {"id": 4, "username": "charlie_sentry", "full_name": "Sgt. David Miller", "callsign": "CHARLIE-SENTRY", "role": "Field Specialist", "unit_id": "C"},
        'D': {"id": 5, "username": "delta_ranger", "full_name": "Cpl. Anya Reyes", "callsign": "DELTA-RANGER", "role": "Field Specialist", "unit_id": "D"},
        'E': {"id": 6, "username": "echo_sentinel", "full_name": "Spec. Jack Cooper", "callsign": "ECHO-SENTINEL", "role": "Field Specialist", "unit_id": "E"},
    }
    sender = simulated_senders.get(source, simulated_senders['CC'])

    data = request.get_json(silent=True) or {}
    message = str(data.get('message', '')).strip()[:500]
    if not message:
        message = f"PRIORITY TRANSMISSION to Station {target}: Inbound telemetry and sector clearance verified. Acknowledge transmission reception."
    priority = data.get('priority', 'High')

    path, cost = shortest_path(source, target)
    status = 'Delivered' if path else 'No route'
    delay = round((cost or 0) * 0.8 + 0.2, 1) if path else 0
    now_time = datetime.now().strftime('%H:%M:%S')

    signature = generate_message_signature(
        sender['username'],
        sender['callsign'],
        source,
        target,
        message,
        now_time
    )

    category = classify(message)

    record = database.add_message(
        sender=sender,
        source=source,
        target=target,
        message=message,
        priority=priority,
        category=category,
        path=path,
        status=status,
        delay=delay,
        signature=signature
    )

    event_text = (
        f"[{sender['callsign']}] Inbound transmission dispatched to {target} via {' → '.join(path)} ({status})"
        if path else
        f"[{sender['callsign']}] Failed inbound transmission {source} → {target} (No route)"
    )
    database.add_event('good' if path else 'bad', event_text, actor=sender['callsign'])

    return jsonify({"message": record, "state": snapshot(current_user)})


@app.post('/api/link')
@login_required
def toggle_link():
    current_user = get_current_user()
    perms = current_user.get('permissions', {})
    if not perms.get('can_toggle_links'):
        return jsonify({
            "error": f"Clearance Denied: Modifying network link infrastructure requires Level 3 Command Officer clearance. Current role: {current_user['role']}."
        }), 403

    data = request.get_json(silent=True) or {}
    a, b = data.get('a'), data.get('b')

    new_active = database.toggle_link_state(a, b)
    if new_active is None:
        return jsonify({"error": "Link not found between specified nodes."}), 404

    event_type = "good" if new_active else "bad"
    state_desc = "restored" if new_active else "simulated failure"
    database.add_event(
        event_type,
        f"Link {a}–{b} {state_desc} by operator [{current_user['callsign']}].",
        actor=current_user['callsign']
    )

    return jsonify(snapshot(current_user))


@app.post('/api/reset')
@login_required
def reset():
    current_user = get_current_user()
    perms = current_user.get('permissions', {})
    if not perms.get('can_reset_links'):
        return jsonify({
            "error": f"Clearance Denied: Restoring all network links requires Level 3 Command Officer clearance. Current role: {current_user['role']}."
        }), 403

    database.reset_all_links()
    database.add_event(
        'good',
        f"All tactical network links restored to active by [{current_user['callsign']}].",
        actor=current_user['callsign']
    )
    return jsonify(snapshot(current_user))


@app.post('/api/summary')
@login_required
def summary():
    current_user = get_current_user()
    perms = current_user.get('permissions', {})
    if not perms.get('can_generate_summary'):
        return jsonify({
            "error": f"Clearance Denied: Generating tactical AI situation summaries requires Level 2+ clearance. Current role: {current_user['role']}."
        }), 403

    data = snapshot(current_user)
    links = data['links']
    messages = data['messages']

    failed_links = [f"{x['a']}–{x['b']}" for x in links if not x['active']]
    delivered = [m for m in messages if m['status'] == 'Delivered']
    failed = [m for m in messages if m['status'] == 'No route']

    if failed_links:
        link_text = ', '.join(failed_links)
    else:
        link_text = 'None; all network links operational'

    if delivered:
        last = delivered[0]
        sender_info = f"Operator [{last['sender']['callsign']}]" if last.get('sender') else "Unknown"
        msg_text = f"Most recent verified transmission by {sender_info} routed via {' → '.join(last['path'])} with delay {last['delay']}s."
    else:
        msg_text = 'No transmissions logged in this operational session.'

    summary_text = (
        f"Tactical Network Health is {data['stats']['uptime']}% with {data['stats']['active']} active links and {data['stats']['failed']} outages. "
        f"Outages: {link_text}. "
        f"Message Registry: {data['stats']['messages']} total transmissions ({data['stats']['delivered']} delivered, {data['stats']['failedMessages']} unrouted). "
        f"{msg_text} Active Watch Officer: {current_user['full_name']} [{current_user['callsign']}] ({current_user['clearance_level']}). "
        f"Cryptographic identity protocols are active."
    )

    database.add_event(
        'good',
        f"Situation summary generated by [{current_user['callsign']}].",
        actor=current_user['callsign']
    )

    return jsonify({"summary": summary_text, "stats": data['stats']})


@app.get('/api/messages/export')
@login_required
def export_messages():
    """Allows downloading tactical message transmission logs for post-mission debriefing."""
    current_user = get_current_user()
    perms = current_user.get('permissions', {})
    if not perms.get('can_export_logs'):
        return jsonify({
            "error": f"Clearance Denied: Exporting mission intelligence logs requires Level 2+ clearance. Current role: {current_user['role']}."
        }), 403

    export_format = request.args.get('format', 'json').lower()
    messages = database.get_messages(limit=200)

    if export_format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Time', 'Sender Callsign', 'Sender Name', 'Sender Role', 'From Unit', 'To Unit', 'Message', 'Priority', 'Category', 'Route Path', 'Status', 'Delay (s)', 'Digital Signature'])
        for m in messages:
            sender = m.get('sender', {})
            path_str = ' -> '.join(m.get('path', [])) if m.get('path') else 'None'
            writer.writerow([
                m.get('id'),
                m.get('time'),
                sender.get('callsign', ''),
                sender.get('name', ''),
                sender.get('role', ''),
                m.get('source'),
                m.get('target'),
                m.get('message'),
                m.get('priority'),
                m.get('category'),
                path_str,
                m.get('status'),
                m.get('delay'),
                m.get('signature')
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=netshield_transmissions.csv"}
        )

    return jsonify({"count": len(messages), "transmissions": messages})


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
