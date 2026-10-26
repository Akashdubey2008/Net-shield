// NetShield Command - Tactical Network Coordination & Identity System
const $ = (id) => document.getElementById(id);

let appState = null;
let currentUser = null;
let lastRoute = [];
let audioEnabled = true;
let lastSeenMessageId = 0;
let currentMailbox = 'all';

const nodeCoords = {
  CC: { name: 'Command Center', x: 50, y: 48, kind: 'command' },
  A:  { name: 'Alpha Unit', x: 18, y: 36, kind: 'unit' },
  B:  { name: 'Bravo Unit', x: 48, y: 13, kind: 'unit' },
  C:  { name: 'Charlie Unit', x: 81, y: 35, kind: 'unit' },
  D:  { name: 'Delta Unit', x: 29, y: 79, kind: 'unit' },
  E:  { name: 'Echo Unit', x: 72, y: 78, kind: 'unit' },
};

const adjacentNodes = {
  CC: ['A', 'B', 'C', 'D', 'E'],
  A: ['CC', 'B', 'D'],
  B: ['CC', 'A', 'C'],
  C: ['CC', 'B', 'E'],
  D: ['CC', 'A', 'E'],
  E: ['CC', 'D', 'C']
};

// ----------------- Tactical Audio Engine (Web Audio API) ----------------- //
let audioCtx = null;

function getAudioContext() {
  if (!audioCtx) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) audioCtx = new AudioContext();
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function playTone(freq, type = 'sine', duration = 0.08, gainVal = 0.05) {
  if (!audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    gain.gain.setValueAtTime(gainVal, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  } catch (e) {
    // Audio context may be restricted by browser policy before user interaction
  }
}

function soundClick() { playTone(880, 'sine', 0.05, 0.03); }
function soundSuccess() {
  playTone(587.33, 'triangle', 0.08, 0.04);
  setTimeout(() => playTone(880, 'triangle', 0.12, 0.04), 90);
}
function soundAlert() {
  playTone(440, 'sawtooth', 0.12, 0.04);
  setTimeout(() => playTone(330, 'sawtooth', 0.15, 0.04), 130);
}
function soundPacket() {
  playTone(1200, 'sine', 0.04, 0.02);
}
function soundIncomingRadio() {
  playTone(523.25, 'triangle', 0.09, 0.06);
  setTimeout(() => playTone(659.25, 'triangle', 0.09, 0.06), 95);
  setTimeout(() => playTone(783.99, 'triangle', 0.16, 0.07), 190);
}

// ----------------- API Request Wrapper ----------------- //
async function api(url, options = {}) {
  const defaultHeaders = { 'Content-Type': 'application/json' };
  const response = await fetch(url, {
    headers: { ...defaultHeaders, ...(options.headers || {}) },
    ...options
  });
  
  if (response.status === 401 && !url.includes('/api/auth/me')) {
    showAuthModal(true);
    throw new Error('Authentication required. Please sign in.');
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || 'Server request failed.');
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function nodeById(id) {
  return (appState && appState.nodes) ? appState.nodes.find(n => n.id === id) : nodeCoords[id];
}

// ----------------- Authentication & Profile UI ----------------- //
function showAuthModal(show = true) {
  const modal = $('authModal');
  if (show) {
    modal.classList.add('active');
  } else {
    modal.classList.remove('active');
  }
}

function showIncomingAlert(m) {
  if (!m) return;
  const targetNode = nodeById(m.target) || { name: m.target, id: m.target };
  const sourceNode = nodeById(m.source) || { name: m.source, id: m.source };
  const sender = m.sender || {};

  $('alertTargetUnit').textContent = `${targetNode.name} (${targetNode.id})`;
  $('alertSourceUnit').textContent = `${sourceNode.name} (${sourceNode.id})`;
  $('alertSenderDetails').textContent = `${sender.name || 'Unknown Operator'} [${sender.callsign || 'ACTUAL'}] • ${sender.role || 'Operator'}`;
  
  const priorityEl = $('alertPriorityPill');
  priorityEl.textContent = m.priority || 'Normal';
  priorityEl.className = 'pill ' + (m.priority === 'Urgent' ? 'urgent' : m.priority === 'High' ? 'high' : '');

  $('alertSigToken').textContent = m.signature || 'SIG-VERIFIED';
  $('alertMessageText').textContent = m.message || '(Empty transmission)';

  const routeContainer = $('alertRouteChips');
  if (m.path && m.path.length) {
    routeContainer.innerHTML = m.path.map((id, i) => `${i ? '<span class="route-arrow">→</span>' : ''}<span class="route-chip">${id}</span>`).join('');
  } else {
    routeContainer.innerHTML = '<span class="muted">No direct route</span>';
  }

  soundIncomingRadio();
  $('incomingAlertModal').classList.add('active');
}

function hideIncomingAlert() {
  const modal = $('incomingAlertModal');
  if (modal) modal.classList.remove('active');
}

function updateOperatorUI(user) {
  if (!user) return;
  currentUser = user;
  const role = user.role || 'Field Specialist';
  const perms = user.permissions || {};
  
  // Topbar Profile
  $('profileCallsign').textContent = user.callsign || 'OPERATOR';
  $('profileUnitTag').textContent = user.unit_id || 'HQ';
  $('profileName').textContent = user.full_name || user.username;
  $('profileRole').textContent = `${user.role || 'Officer'} • ${user.clearance_level ? user.clearance_level.split('-')[0].trim() : 'Clearance Active'}`;
  $('authStatusText').textContent = `Logged in: ${user.callsign}`;

  const avatar = $('profileAvatar');
  if (avatar) {
    avatar.textContent = role === 'Command Officer' ? '🎖️' : role === 'Communications Officer' ? '📡' : '🛡️';
  }

  const powerPill = $('opPowerPill');
  if (powerPill) {
    if (role === 'Command Officer') {
      powerPill.textContent = 'LEVEL 3: FULL COMMAND';
      powerPill.className = 'op-power-pill level3';
    } else if (role === 'Communications Officer') {
      powerPill.textContent = 'LEVEL 2: TACTICAL COMMS';
      powerPill.className = 'op-power-pill level2';
    } else {
      powerPill.textContent = 'LEVEL 1: FIELD STATION';
      powerPill.className = 'op-power-pill level1';
    }
  }

  // Communication Banner
  $('bannerOpName').textContent = user.full_name || user.username;
  $('bannerOpCallsign').textContent = user.callsign || 'HQ';
  $('bannerOpRole').textContent = user.role || 'Officer';
  $('bannerOpUnit').textContent = `${nodeCoords[user.unit_id] ? nodeCoords[user.unit_id].name : 'Command HQ'} (${user.unit_id})`;

  // Mailbox tabs unit indicators
  const boxSentUnit = $('boxSentUnit');
  const boxReceivedUnit = $('boxReceivedUnit');
  if (boxSentUnit) boxSentUnit.textContent = user.unit_id || 'HQ';
  if (boxReceivedUnit) boxReceivedUnit.textContent = user.unit_id || 'HQ';

  // Role Permissions Matrix Bar
  const rpbClearance = $('rpbClearance');
  const rpbOrigins = $('rpbOrigins');
  const rpbDestinations = $('rpbDestinations');
  const rpbPriorities = $('rpbPriorities');
  const rpbBroadcast = $('rpbBroadcast');

  if (rpbClearance) rpbClearance.textContent = user.clearance_level || 'Level 1 - Confidential';
  if (rpbOrigins) {
    rpbOrigins.textContent = role === 'Command Officer' 
      ? 'All Stations (CC, A, B, C, D, E)'
      : role === 'Communications Officer'
      ? `Assigned Unit (${user.unit_id}) & Command Center (CC)`
      : `Locked to Assigned Unit (${user.unit_id})`;
  }
  if (rpbDestinations) {
    rpbDestinations.textContent = role === 'Field Specialist'
      ? 'Command Center & Direct Radio Neighbors'
      : 'Full Network (All Stations via Dijkstra)';
  }
  if (rpbPriorities) {
    rpbPriorities.textContent = role === 'Command Officer'
      ? 'Urgent Flash, High, Normal, Low'
      : role === 'Communications Officer'
      ? 'High, Normal, Low'
      : 'Normal, Low Only';
  }
  if (rpbBroadcast) {
    rpbBroadcast.textContent = perms.can_broadcast 
      ? 'Authorized (Flash Override)' 
      : 'Restricted (Requires Level 3 Command)';
  }

  // Fleet Broadcast Action (Command Officer only)
  const broadcastBtn = $('broadcastBtn');
  if (broadcastBtn) {
    broadcastBtn.style.display = perms.can_broadcast ? 'inline-flex' : 'none';
  }

  // Network Failure Simulation (Command Officer only)
  const failRandom = $('failRandom');
  const restoreAll = $('restoreAll');
  const restoreAll2 = $('restoreAll2');
  const isCommand = (role === 'Command Officer');
  
  if (failRandom) {
    failRandom.disabled = !isCommand;
    failRandom.title = isCommand ? 'Simulate tactical link failure' : 'Modifying network links requires Level 3 Command Officer clearance';
    failRandom.classList.toggle('btn-disabled', !isCommand);
  }
  if (restoreAll) {
    restoreAll.disabled = !isCommand;
    restoreAll.title = isCommand ? 'Restore all links' : 'Requires Level 3 Command Officer clearance';
    restoreAll.classList.toggle('btn-disabled', !isCommand);
  }
  if (restoreAll2) {
    restoreAll2.disabled = !isCommand;
    restoreAll2.title = isCommand ? 'Restore all links' : 'Requires Level 3 Command Officer clearance';
    restoreAll2.classList.toggle('btn-disabled', !isCommand);
  }

  // Situation summary (Level 2+ clearance)
  const generateSummary = $('generateSummary');
  if (generateSummary) {
    const canSummary = Boolean(perms.can_generate_summary);
    generateSummary.disabled = !canSummary;
    generateSummary.title = canSummary ? 'Generate situation assessment' : 'Requires Level 2+ Clearance';
    generateSummary.classList.toggle('btn-disabled', !canSummary);
  }

  // Export buttons (Level 2+ clearance)
  const exportCsvBtn = $('exportCsvBtn');
  const exportJsonBtn = $('exportJsonBtn');
  const canExport = Boolean(perms.can_export_logs);
  if (exportCsvBtn) {
    exportCsvBtn.disabled = !canExport;
    exportCsvBtn.title = canExport ? 'Export message log as CSV' : 'Requires Level 2+ Clearance';
    exportCsvBtn.classList.toggle('btn-disabled', !canExport);
  }
  if (exportJsonBtn) {
    exportJsonBtn.disabled = !canExport;
    exportJsonBtn.title = canExport ? 'Export message log as JSON' : 'Requires Level 2+ Clearance';
    exportJsonBtn.classList.toggle('btn-disabled', !canExport);
  }
}

// ----------------- Map Rendering & Packet Animation ----------------- //
function drawMap() {
  const svg = $('linkSvg');
  svg.innerHTML = '';
  const ns = 'http://www.w3.org/2000/svg';

  // Draw links
  appState.links.forEach(link => {
    const a = nodeById(link.a), b = nodeById(link.b);
    if (!a || !b) return;
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', a.x);
    line.setAttribute('y1', a.y);
    line.setAttribute('x2', b.x);
    line.setAttribute('y2', b.y);

    const inRoute = lastRoute.length > 1 && lastRoute.some((id, i) =>
      i < lastRoute.length - 1 &&
      ((id === link.a && lastRoute[i + 1] === link.b) || (id === link.b && lastRoute[i + 1] === link.a))
    );

    line.setAttribute('class', 'link-line ' + (!link.active ? 'failed-link' : inRoute ? 'route-link' : 'active-link'));
    line.setAttribute('vector-effect', 'non-scaling-stroke');
    line.setAttribute('title', `${link.a} ↔ ${link.b} (${link.active ? 'Active' : 'Failed'} - Cost: ${link.weight.toFixed(1)})`);
    line.addEventListener('click', () => {
      soundClick();
      toggleLink(link.a, link.b);
    });
    svg.appendChild(line);
  });

  // Render nodes
  const layer = $('nodeLayer');
  layer.innerHTML = '';
  appState.nodes.forEach(node => {
    const el = document.createElement('div');
    el.className = 'node ' + (node.kind === 'command' ? 'command' : '');
    el.style.left = node.x + '%';
    el.style.top = node.y + '%';
    el.innerHTML = `
      <div class="node-circle">${node.kind === 'command' ? '✦' : '●'}</div>
      <div class="node-label">${escapeHtml(node.name)}<br><span style="color:#83a1b8;font-weight:700">${node.id}</span></div>
    `;
    layer.appendChild(el);
  });
}

function animatePacketFlow(path) {
  if (!path || path.length < 2) return;
  const svg = $('linkSvg');
  const ns = 'http://www.w3.org/2000/svg';

  // Remove existing packet elements
  svg.querySelectorAll('.animated-packet').forEach(el => el.remove());

  const packet = document.createElementNS(ns, 'circle');
  packet.setAttribute('r', '1.6');
  packet.setAttribute('class', 'animated-packet');
  svg.appendChild(packet);

  let hopIndex = 0;
  const hops = [];
  for (let i = 0; i < path.length - 1; i++) {
    const fromNode = nodeById(path[i]);
    const toNode = nodeById(path[i + 1]);
    if (fromNode && toNode) {
      hops.push({ from: fromNode, to: toNode });
    }
  }

  if (!hops.length) return;

  function runHop() {
    if (hopIndex >= hops.length) {
      setTimeout(() => packet.remove(), 600);
      return;
    }
    const current = hops[hopIndex];
    const startTime = performance.now();
    const duration = 400; // ms per hop
    soundPacket();

    function step(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const curX = current.from.x + (current.to.x - current.from.x) * progress;
      const curY = current.from.y + (current.to.y - current.from.y) * progress;
      packet.setAttribute('cx', curX);
      packet.setAttribute('cy', curY);

      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        hopIndex++;
        runHop();
      }
    }
    requestAnimationFrame(step);
  }

  runHop();
}

// ----------------- Dashboard & Tables Rendering ----------------- //
function renderEvents() {
  const container = $('eventList');
  if (!appState.events || !appState.events.length) {
    container.innerHTML = '<p class="muted" style="padding:15px;text-align:center;">No tactical events logged yet.</p>';
    return;
  }
  container.innerHTML = appState.events.map(e => `
    <div class="event-item">
      <i class="event-bullet ${e.type === 'bad' ? 'bad' : ''}"></i>
      <div>
        <p>${e.actor ? `<span class="event-actor">[${escapeHtml(e.actor)}]</span>` : ''}${escapeHtml(e.text)}</p>
        <time>${escapeHtml(e.time)}</time>
      </div>
    </div>
  `).join('');
}

function renderMessages() {
  const filterPriority = $('filterPriority').value;
  const filterStatus = $('filterStatus').value;
  const searchTerm = $('logSearch').value.trim().toLowerCase();

  let messages = appState.messages || [];

  // Filter by Station Mailbox (All / Sent / Received)
  if (currentUser) {
    if (currentMailbox === 'sent') {
      messages = messages.filter(m => m.source === currentUser.unit_id);
    } else if (currentMailbox === 'received') {
      messages = messages.filter(m => m.target === currentUser.unit_id);
    }
  }

  const pill = $('mailboxStatsPill');
  if (pill && currentUser) {
    if (currentMailbox === 'sent') {
      pill.textContent = `Showing ${messages.length} outbound transmissions sent from ${currentUser.unit_id}`;
    } else if (currentMailbox === 'received') {
      pill.textContent = `Showing ${messages.length} inbound transmissions received at ${currentUser.unit_id}`;
    } else {
      pill.textContent = `Showing all ${messages.length} fleet transmissions`;
    }
  }

  if (filterPriority) {
    messages = messages.filter(m => m.priority === filterPriority);
  }
  if (filterStatus) {
    messages = messages.filter(m => m.status === filterStatus);
  }
  if (searchTerm) {
    messages = messages.filter(m => {
      const text = (m.message || '').toLowerCase();
      const callsign = (m.sender?.callsign || '').toLowerCase();
      const name = (m.sender?.name || '').toLowerCase();
      const sig = (m.signature || '').toLowerCase();
      const src = (m.source || '').toLowerCase();
      const tgt = (m.target || '').toLowerCase();
      return text.includes(searchTerm) || callsign.includes(searchTerm) || name.includes(searchTerm) || sig.includes(searchTerm) || src.includes(searchTerm) || tgt.includes(searchTerm);
    });
  }

  const rows = messages.map(m => {
    const sender = m.sender || {};
    const priorityClass = m.priority === 'Urgent' ? 'urgent' : m.priority === 'High' ? 'high' : '';
    const statusClass = m.status === 'Delivered' ? '' : 'bad';
    const pathText = (m.path && m.path.length) ? m.path.join(' → ') : '—';

    const isSent = currentUser && (m.source === currentUser.unit_id);
    const isReceived = currentUser && (m.target === currentUser.unit_id);
    const dirBadge = isSent 
      ? '<span class="dir-badge sent" title="Sent by your station">↗ OUTBOUND</span>' 
      : isReceived 
      ? '<span class="dir-badge received" title="Received at your station">↙ INBOUND</span>' 
      : '<span class="dir-badge transit" title="Transit / Fleet transmission">TRANSIT</span>';

    const srcNode = nodeById(m.source) || { name: m.source, id: m.source };
    const tgtNode = nodeById(m.target) || { name: m.target, id: m.target };

    return `
      <tr>
        <td>${escapeHtml(m.time)}</td>
        <td>${dirBadge}</td>
        <td>
          <div class="op-log-badge">
            <span class="op-log-callsign">⬡ ${escapeHtml(sender.callsign || 'UNIDENTIFIED')}</span>
            <span class="op-log-name">${escapeHtml(sender.name || 'Unknown')} [${escapeHtml(sender.unit || '-')}]</span>
          </div>
        </td>
        <td>
          <div class="station-route-cell">
            <span class="station-chip from" title="Origin Station">${escapeHtml(srcNode.name)} (${escapeHtml(m.source)})</span>
            <span class="route-arrow">→</span>
            <span class="station-chip to" title="Recipient Station">${escapeHtml(tgtNode.name)} (${escapeHtml(m.target)})</span>
          </div>
        </td>
        <td>
          ${escapeHtml(m.message)}<br>
          <small style="color:#7e95aa">${escapeHtml(m.category)}</small>
        </td>
        <td><span class="pill ${priorityClass}">${escapeHtml(m.priority)}</span></td>
        <td>${escapeHtml(pathText)}</td>
        <td><span class="sig-token" title="Cryptographic Identity Signature">${escapeHtml(m.signature || 'SIG-VERIFIED')}</span></td>
        <td><span class="pill ${statusClass}">${escapeHtml(m.status)}</span></td>
      </tr>
    `;
  }).join('');

  $('messageRows').innerHTML = rows || '<tr><td colspan="9" style="color:#8199ae;text-align:center;padding:26px">No transmissions matching current criteria.</td></tr>';
}

function renderLinks() {
  const isCommand = currentUser && (currentUser.role === 'Command Officer');
  const container = $('linkCards');
  container.innerHTML = appState.links.map(l => `
    <div class="link-card">
      <div>
        <b>${l.a} ↔ ${l.b}</b>
        <small>Simulated Dijkstra Cost: ${l.weight.toFixed(1)}</small>
      </div>
      <div>
        <span class="link-status ${l.active ? 'on' : 'off'}">${l.active ? '● OPERATIONAL' : '● OUTAGE'}</span>
        <button class="btn btn-quiet ${!isCommand ? 'btn-disabled' : ''}" data-a="${l.a}" data-b="${l.b}" ${!isCommand ? 'disabled title="Requires Level 3 Command Officer Clearance"' : ''}>
          ${!isCommand ? '🔒 Restricted' : (l.active ? 'Simulate Outage' : 'Restore Link')}
        </button>
      </div>
    </div>
  `).join('');

  if (isCommand) {
    container.querySelectorAll('button').forEach(b => {
      b.addEventListener('click', () => {
        soundClick();
        toggleLink(b.dataset.a, b.dataset.b);
      });
    });
  }
}

function renderStats() {
  const s = appState.stats;
  $('unitCount').textContent = s.units;
  $('activeCount').textContent = s.active;
  $('failedCount').textContent = s.failed;
  $('uptime').textContent = s.uptime + '%';

  $('totalMessages').textContent = s.messages;
  $('deliveredMessages').textContent = s.delivered;
  $('failedMessages').textContent = s.failedMessages;
  $('averageDelay').textContent = s.avgDelay + ' s';
}

function fillSelects() {
  const source = $('source');
  const target = $('target');
  const priority = $('priority');
  const role = currentUser ? (currentUser.role || 'Field Specialist') : 'Field Specialist';
  const unitId = currentUser ? (currentUser.unit_id || 'A') : 'A';

  // 1. Configure Source (Origin) dropdown
  if (role === 'Field Specialist') {
    source.innerHTML = `<option value="${unitId}">${nodeCoords[unitId]?.name || 'Your Station'} (${unitId}) [LOCKED TO YOUR STATION]</option>`;
    source.value = unitId;
    source.disabled = true;
    const hint = $('sourceHint');
    if (hint) hint.textContent = `🔒 Station Lock: Field Specialists can only originate transmissions from assigned station (${unitId}).`;
  } else if (role === 'Communications Officer') {
    source.disabled = false;
    const oldSource = source.value;
    source.innerHTML = `
      <option value="${unitId}">${nodeCoords[unitId]?.name || 'Assigned Station'} (${unitId}) [Your Station]</option>
      <option value="CC">Command Center (CC)</option>
    `;
    if (oldSource === 'CC' || oldSource === unitId) {
      source.value = oldSource;
    } else {
      source.value = unitId;
    }
    const hint = $('sourceHint');
    if (hint) hint.textContent = `Clearance Level 2: Authorized to dispatch from assigned station (${unitId}) or Command Center (CC).`;
  } else {
    source.disabled = false;
    const oldSource = source.value;
    source.innerHTML = appState.nodes.map(n => `<option value="${n.id}">${n.name} (${n.id})</option>`).join('');
    if (appState.nodes.some(n => n.id === oldSource)) {
      source.value = oldSource;
    }
    const hint = $('sourceHint');
    if (hint) hint.textContent = `Level 3 Command Clearance: Authorized to dispatch on behalf of any fleet unit.`;
  }

  // 2. Configure Target (Destination) dropdown
  const currentSourceVal = (role === 'Field Specialist') ? unitId : (source.value || 'CC');
  let allowedTargets = appState.nodes;

  if (role === 'Field Specialist') {
    const neighbors = adjacentNodes[currentSourceVal] || ['CC'];
    allowedTargets = appState.nodes.filter(n => neighbors.includes(n.id));
    const hint = $('targetHint');
    if (hint) hint.textContent = `Point-to-point field horizon: Command Center (CC) or direct neighbor units (${neighbors.join(', ')}).`;
  } else {
    allowedTargets = appState.nodes.filter(n => n.id !== currentSourceVal);
    const hint = $('targetHint');
    if (hint) hint.textContent = `Tactical mesh range: Dynamic Dijkstra routing across all units.`;
  }

  const oldTarget = target.value;
  target.innerHTML = allowedTargets.map(n => `<option value="${n.id}">${n.name} (${n.id})</option>`).join('');
  if (allowedTargets.some(n => n.id === oldTarget)) {
    target.value = oldTarget;
  } else if (allowedTargets.length) {
    target.value = allowedTargets[0].id;
  }

  // 3. Configure Priority dropdown
  const oldPriority = priority.value;
  if (role === 'Field Specialist') {
    priority.innerHTML = `
      <option value="Normal">Normal</option>
      <option value="Low">Low</option>
    `;
    const hint = $('priorityHint');
    if (hint) hint.textContent = `Standard field transmission (Normal and Low priority only).`;
  } else if (role === 'Communications Officer') {
    priority.innerHTML = `
      <option value="High">High</option>
      <option value="Normal">Normal</option>
      <option value="Low">Low</option>
    `;
    const hint = $('priorityHint');
    if (hint) hint.textContent = `Tactical comms priority tier (High, Normal, and Low priorities).`;
  } else {
    priority.innerHTML = `
      <option value="Urgent">Urgent (Tactical Flash Override)</option>
      <option value="High">High</option>
      <option value="Normal">Normal</option>
      <option value="Low">Low</option>
    `;
    const hint = $('priorityHint');
    if (hint) hint.textContent = `Level 3 Flash Override: Authorized for all priority levels including Urgent Alert.`;
  }
  if (Array.from(priority.options).some(o => o.value === oldPriority)) {
    priority.value = oldPriority;
  }
}

function render() {
  renderStats();
  drawMap();
  renderEvents();
  renderMessages();
  renderLinks();
  fillSelects();
}

// ----------------- Actions & Server Sync ----------------- //
async function refresh() {
  appState = await api('/api/state');
  if (appState.currentUser) {
    updateOperatorUI(appState.currentUser);
  }
  if (appState.messages && appState.messages.length) {
    lastSeenMessageId = Math.max(lastSeenMessageId, ...appState.messages.map(m => m.id));
  }
  render();
}

async function toggleLink(a, b) {
  try {
    appState = await api('/api/link', { method: 'POST', body: JSON.stringify({ a, b }) });
    render();
  } catch (e) {
    alert(e.message);
  }
}

async function restoreAll() {
  try {
    soundClick();
    appState = await api('/api/reset', { method: 'POST', body: '{}' });
    lastRoute = [];
    render();
    soundSuccess();
  } catch (e) {
    alert(e.message);
  }
}

function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === page));
  document.querySelectorAll('.nav').forEach(n => n.classList.toggle('active', n.dataset.page === page));
  const titles = {
    dashboard: 'Operations dashboard',
    communication: 'Tactical Communication & Message Dispatch',
    network: 'Tactical Network Link Matrix',
    reports: 'AI-Style Situation Assessment & Reports'
  };
  $('pageTitle').textContent = titles[page] || titles.dashboard;
}

// ----------------- Event Listeners ----------------- //
document.querySelectorAll('.nav').forEach(btn => {
  btn.addEventListener('click', () => {
    soundClick();
    showPage(btn.dataset.page);
  });
});

$('failRandom').addEventListener('click', async () => {
  soundClick();
  const active = appState.links.filter(l => l.active);
  if (!active.length) {
    soundAlert();
    alert('All tactical links are already in outage state. Restore links first.');
    return;
  }
  const l = active[Math.floor(Math.random() * active.length)];
  await toggleLink(l.a, l.b);
  soundAlert();
});

$('restoreAll').addEventListener('click', restoreAll);
$('restoreAll2').addEventListener('click', restoreAll);

// Audio FX Toggle
$('toggleAudio').addEventListener('click', () => {
  audioEnabled = !audioEnabled;
  $('toggleAudio').textContent = audioEnabled ? '🔊' : '🔇';
  $('toggleAudio').title = audioEnabled ? 'Mute Tactical Audio' : 'Enable Tactical Audio';
  if (audioEnabled) soundClick();
});

// Update targets when source changes
$('source').addEventListener('change', () => {
  fillSelects();
});

// Message Form Submission
$('messageForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const feedback = $('formFeedback');
  feedback.className = 'feedback';
  feedback.textContent = 'Computing Dijkstra shortest path & signing packet…';

  const sourceVal = (currentUser && currentUser.role === 'Field Specialist') ? currentUser.unit_id : $('source').value;
  const targetVal = $('target').value;
  const priorityVal = $('priority').value;
  const messageVal = $('messageText').value;

  try {
    const result = await api('/api/message', {
      method: 'POST',
      body: JSON.stringify({
        source: sourceVal,
        target: targetVal,
        priority: priorityVal,
        message: messageVal
      })
    });

    appState = result.state;
    const m = result.message;
    lastRoute = m.path || [];
    render();

    // Trigger packet animation along route
    if (m.status === 'Delivered') {
      soundSuccess();
      animatePacketFlow(m.path);
    } else {
      soundAlert();
    }

    $('transmissionEmpty').hidden = true;
    $('transmissionResult').hidden = false;
    $('transmissionResult').innerHTML = `
      <div class="result-banner ${m.status === 'Delivered' ? '' : 'failed'}">
        <span>${m.status === 'Delivered' ? '✓ Message Delivered' : '! Transmission Failed (No Route)'}</span>
        <span class="verified-seal-pill">${escapeHtml(m.signature || 'VERIFIED')}</span>
      </div>
      <div class="route-chips">
        ${m.path.length ? m.path.map((id, i) => `${i ? '<span class="route-arrow">→</span>' : ''}<span class="route-chip">${id}</span>`).join('') : '<span>No route available through active topology links.</span>'}
      </div>
      <div class="detail-list">
        <div class="detail-row"><span>Authenticated Operator</span><b>${escapeHtml(m.sender?.name || 'Operator')} [${escapeHtml(m.sender?.callsign || 'ACTUAL')}]</b></div>
        <div class="detail-row"><span>Clearance & Role</span><b>${escapeHtml(m.sender?.role || 'Officer')}</b></div>
        <div class="detail-row"><span>Incident Classification</span><b>${escapeHtml(m.category)}</b></div>
        <div class="detail-row"><span>Priority Level</span><b>${escapeHtml(m.priority)}</b></div>
        <div class="detail-row"><span>Estimated Latency</span><b>${m.delay} seconds</b></div>
        <div class="detail-row"><span>Dijkstra Path Hops</span><b>${m.path.length ? (m.path.length - 1) + ' hops' : 'None'}</b></div>
      </div>
    `;

    feedback.textContent = m.status === 'Delivered'
      ? 'Transmission signed and verified along calculated Dijkstra path.'
      : 'Network partition: Dijkstra pathfinding found no viable route with current active links.';
    $('messageText').value = '';
    lastSeenMessageId = Math.max(lastSeenMessageId, m.id);
    showPage('communication');

    if (m.target === currentUser.unit_id && m.status === 'Delivered') {
      showIncomingAlert(m);
    }
  } catch (err) {
    soundAlert();
    feedback.className = 'feedback error';
    feedback.textContent = err.message;
  }
});

// Simulate Inbound Message to Current Operator Unit
const simInboundBtn = $('simulateIncomingBtn');
if (simInboundBtn) {
  simInboundBtn.addEventListener('click', async () => {
    try {
      soundClick();
      const result = await api('/api/message/simulate-incoming', { method: 'POST', body: '{}' });
      appState = result.state;
      lastRoute = result.message.path || [];
      lastSeenMessageId = Math.max(lastSeenMessageId, result.message.id);
      render();

      if (result.message.status === 'Delivered') {
        animatePacketFlow(result.message.path);
      }
      showIncomingAlert(result.message);
    } catch (err) {
      soundAlert();
      alert('Could not simulate inbound transmission: ' + err.message);
    }
  });
}

// Incoming Alert Modal Actions
const alertCloseBtn = $('alertCloseBtn');
const alertAckBtn = $('alertAckBtn');
const alertViewLogBtn = $('alertViewLogBtn');

if (alertCloseBtn) {
  alertCloseBtn.addEventListener('click', () => {
    soundClick();
    hideIncomingAlert();
  });
}
if (alertAckBtn) {
  alertAckBtn.addEventListener('click', () => {
    soundSuccess();
    hideIncomingAlert();
  });
}
if (alertViewLogBtn) {
  alertViewLogBtn.addEventListener('click', () => {
    soundClick();
    hideIncomingAlert();
    showPage('communication');
    const table = $('messageRows');
    if (table) {
      table.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
}

// Background Polling for Incoming Station Transmissions
setInterval(async () => {
  if (!currentUser) return;
  try {
    const latestState = await api('/api/state');
    if (!latestState || !latestState.messages) return;

    const newMessages = latestState.messages.filter(m => m.id > lastSeenMessageId);
    if (newMessages.length > 0) {
      // Find if any new transmission was addressed to this operator's unit
      const incomingForMe = newMessages.find(m => m.target === currentUser.unit_id);

      appState = latestState;
      lastSeenMessageId = Math.max(lastSeenMessageId, ...latestState.messages.map(m => m.id));
      render();

      if (incomingForMe) {
        showIncomingAlert(incomingForMe);
      }
    }
  } catch (e) {
    // Ignore transient poll interruptions
  }
}, 3500);

// Priority Broadcast Action
$('broadcastBtn').addEventListener('click', async () => {
  const confirmed = confirm('Broadcast Urgent Alert from Command Center to ALL operational units?');
  if (!confirmed) return;

  try {
    soundClick();
    const result = await api('/api/broadcast', {
      method: 'POST',
      body: JSON.stringify({ message: 'PRIORITY FLASH: Tactical command broadcast. All units verify link readiness and report status.' })
    });
    appState = result.state;
    render();
    soundSuccess();
    alert(result.summary);
  } catch (err) {
    soundAlert();
    alert(err.message);
  }
});

// Generate AI Summary
$('generateSummary').addEventListener('click', async () => {
  soundClick();
  const box = $('summaryBox');
  box.innerHTML = '<div class="ai-icon">AI</div><div><b>Analyzing simulation telemetry…</b></div>';
  try {
    const data = await api('/api/summary', { method: 'POST', body: '{}' });
    box.innerHTML = `
      <div class="ai-icon">AI</div>
      <div>
        <b>Situational Assessment</b>
        <p>${escapeHtml(data.summary)}</p>
      </div>
    `;
    appState = await api('/api/state');
    renderStats();
    soundSuccess();
  } catch (e) {
    box.textContent = e.message;
    soundAlert();
  }
});

// Search & Filter Listeners
$('logSearch').addEventListener('input', renderMessages);
$('filterPriority').addEventListener('change', renderMessages);
$('filterStatus').addEventListener('change', renderMessages);

// Station Mailbox Filter Tabs (All / Sent / Received)
document.querySelectorAll('.mailbox-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    soundClick();
    document.querySelectorAll('.mailbox-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentMailbox = tab.dataset.box;
    renderMessages();
  });
});

// Export CSV & JSON
$('exportCsvBtn').addEventListener('click', () => {
  soundClick();
  window.location.href = '/api/messages/export?format=csv';
});

$('exportJsonBtn').addEventListener('click', async () => {
  soundClick();
  const data = await api('/api/messages/export?format=json');
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'netshield_transmissions.json';
  a.click();
  URL.revokeObjectURL(url);
});

// ----------------- Auth Modal Tab & Form Handling ----------------- //
$('tabSignIn').addEventListener('click', () => {
  soundClick();
  $('tabSignIn').classList.add('active');
  $('tabRegister').classList.remove('active');
  $('loginForm').classList.add('active');
  $('registerForm').classList.remove('active');
});

$('tabRegister').addEventListener('click', () => {
  soundClick();
  $('tabRegister').classList.add('active');
  $('tabSignIn').classList.remove('active');
  $('registerForm').classList.add('active');
  $('loginForm').classList.remove('active');
});

async function doLogin(username, password) {
  const feedback = $('loginFeedback');
  feedback.className = 'feedback';
  feedback.textContent = 'Verifying security credentials…';

  try {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    currentUser = data.user;
    appState = data.state;
    updateOperatorUI(currentUser);
    showAuthModal(false);
    render();
    soundSuccess();
  } catch (err) {
    soundAlert();
    feedback.className = 'feedback error';
    feedback.textContent = err.message;
  }
}

$('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const u = $('loginUsername').value.trim();
  const p = $('loginPassword').value;
  await doLogin(u, p);
});

$('registerForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const feedback = $('regFeedback');
  feedback.className = 'feedback';
  feedback.textContent = 'Registering credentials and assigning tactical clearance…';

  const username = $('regUsername').value.trim();
  const password = $('regPassword').value;
  const full_name = $('regFullName').value.trim();
  const callsign = $('regCallsign').value.trim();
  const unit_id = $('regUnitId').value;
  const role = $('regRole').value;

  try {
    const data = await api('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, full_name, callsign, unit_id, role })
    });
    currentUser = data.user;
    appState = data.state;
    updateOperatorUI(currentUser);
    showAuthModal(false);
    render();
    soundSuccess();
  } catch (err) {
    soundAlert();
    feedback.className = 'feedback error';
    feedback.textContent = err.message;
  }
});

// Logout Handler
$('logoutBtn').addEventListener('click', async () => {
  soundClick();
  try {
    await api('/api/auth/logout', { method: 'POST', body: '{}' });
  } catch (e) {
    // Continue cleanup even if server error
  }
  currentUser = null;
  appState = null;
  lastRoute = [];
  $('loginUsername').value = '';
  $('loginPassword').value = '';
  $('loginFeedback').textContent = '';
  $('tabSignIn').click();
  showAuthModal(true);
});

// ----------------- App Boot Sequence ----------------- //
async function initApp() {
  try {
    const authStatus = await api('/api/auth/me');
    if (authStatus && authStatus.authenticated) {
      currentUser = authStatus.user;
      showAuthModal(false);
      await refresh();
    } else {
      showAuthModal(true);
    }
  } catch (err) {
    showAuthModal(true);
  }
}

initApp();
