import uiModule from './ui.js';
import { makeWindowDraggable } from './windowDrag.js';

let API_BASE = window.location.origin;
let sessionModule = null;
let chatModule = null;
let _open = false;
let _runs = [];
let _selectedId = null;
let _filter = 'active';
let _poll = null;
let _escHandler = null;
let _detailStream = null;
let _detailStreamId = null;
let _refreshTimer = null;

const ACTIVE = new Set(['queued', 'running', 'paused', 'waiting_for_approval', 'blocked']);

function _html(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
  }[ch]));
}

function _statusLabel(status) {
  return String(status || 'running').replace(/_/g, ' ');
}

function _typeLabel(type) {
  return {
    agent: 'Agent',
    background_shell: 'Shell',
    research: 'Research',
    scheduled_task: 'Task',
    skill_audit: 'Skill',
    learning_review: 'Learning',
  }[type] || type || 'Run';
}

function _capabilities(run) {
  const caps = run?.metadata?.capabilities || {};
  return {
    cancel: caps.cancel !== false,
    pause: Boolean(caps.pause),
    resume: caps.resume !== false,
    inputs: Boolean(caps.inputs),
    subruns: Boolean(caps.subruns),
    artifacts: caps.artifacts !== false,
    restart_recovery: caps.restart_recovery || run?.metadata?.restart_recovery || '',
    durability: caps.durability || run?.metadata?.durability_scope || '',
  };
}

function _timeLabel(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const delta = Date.now() - d.getTime();
  if (delta < 60_000) return 'now';
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m`;
  if (delta < 86_400_000) return `${Math.floor(delta / 3_600_000)}h`;
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

async function _fetchRuns() {
  const params = new URLSearchParams({ limit: '150' });
  if (_filter === 'active') params.set('active', 'true');
  const res = await fetch(`${API_BASE}/api/runs?${params}`, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`Runs fetch failed (${res.status})`);
  const data = await res.json();
  _runs = data.runs || [];
  _syncBadges(data.active_count ?? _runs.filter(r => ACTIVE.has(r.status)).length);
  if (!_selectedId || !_runs.some(r => r.id === _selectedId)) {
    _selectedId = (_runs[0] || {}).id || null;
  }
  return data;
}

async function _fetchRun(id) {
  if (!id) return null;
  const res = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(id)}`, { credentials: 'same-origin' });
  if (!res.ok) return null;
  return await res.json();
}

function _scheduleRefresh(delay = 250) {
  if (_refreshTimer) clearTimeout(_refreshTimer);
  _refreshTimer = setTimeout(() => {
    _refreshTimer = null;
    refreshRuns();
  }, delay);
}

function _closeRunStream() {
  if (_detailStream) {
    try { _detailStream.close(); } catch {}
  }
  _detailStream = null;
  _detailStreamId = null;
}

function _connectRunStream(runId) {
  if (!runId || typeof EventSource === 'undefined') return;
  if (_detailStream && _detailStreamId === runId) return;
  _closeRunStream();
  try {
    _detailStream = new EventSource(`${API_BASE}/api/runs/${encodeURIComponent(runId)}/stream`);
    _detailStreamId = runId;
    _detailStream.addEventListener('run_event', () => _scheduleRefresh());
    _detailStream.addEventListener('run_snapshot', () => _scheduleRefresh());
    _detailStream.onerror = () => {
      _closeRunStream();
    };
  } catch {
    _closeRunStream();
  }
}

function _syncBadges(count) {
  const n = Number(count || 0);
  const text = n > 99 ? '99+' : String(n);
  for (const id of ['runs-rail-count', 'runs-sidebar-count']) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (n > 0) {
      el.textContent = text;
      el.style.display = '';
    } else {
      el.textContent = '';
      el.style.display = 'none';
    }
  }
  document.getElementById('rail-runs')?.classList.toggle('runs-active', n > 0);
  document.getElementById('tool-runs-btn')?.classList.toggle('runs-active', n > 0);
}

function _renderList() {
  const list = document.getElementById('runs-list');
  if (!list) return;
  if (!_runs.length) {
    list.innerHTML = `<div class="runs-empty">No ${_filter === 'active' ? 'active ' : ''}runs.</div>`;
    return;
  }
  list.innerHTML = _runs.map(run => `
    <button class="runs-row ${run.id === _selectedId ? 'active' : ''}" data-run-id="${_html(run.id)}" type="button">
      <span class="runs-status-dot runs-status-${_html(run.status)}"></span>
      <span class="runs-row-main">
        <span class="runs-row-title">${_html(run.title || 'Untitled run')}</span>
        <span class="runs-row-meta">${_html(_typeLabel(run.run_type))} · ${_html(_statusLabel(run.status))}${run.current_step ? ` · ${_html(run.current_step)}` : ''}</span>
      </span>
      <span class="runs-row-time">${_html(_timeLabel(run.updated_at || run.created_at))}</span>
    </button>
  `).join('');
  list.querySelectorAll('[data-run-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      _selectedId = btn.dataset.runId;
      _renderList();
      _renderDetail();
    });
  });
}

function _eventMarkup(event) {
  const pending = event.approval_id && event.approval_status === 'pending';
  const payload = event.payload && Object.keys(event.payload).length
    ? `<pre class="runs-event-payload">${_html(JSON.stringify(event.payload, null, 2))}</pre>`
    : '';
  return `
    <div class="runs-event">
      <div class="runs-event-head">
        <span>${_html(event.event_type || 'event')}</span>
        <time>${_html(_timeLabel(event.created_at))}</time>
      </div>
      <div class="runs-event-msg">${_html(event.message || '')}</div>
      ${payload}
      ${pending ? `
        <div class="runs-approval-actions">
          <button type="button" class="runs-action primary" data-approve="${_html(event.approval_id)}">Approve</button>
          <button type="button" class="runs-action" data-reject="${_html(event.approval_id)}">Reject</button>
        </div>
      ` : ''}
    </div>
  `;
}

async function _renderDetail() {
  const detail = document.getElementById('runs-detail');
  if (!detail) return;
  if (!_selectedId) {
    detail.innerHTML = '<div class="runs-empty detail">Select a run.</div>';
    return;
  }
  detail.innerHTML = '<div class="runs-empty detail">Loading…</div>';
  const run = await _fetchRun(_selectedId);
  if (!run) {
    detail.innerHTML = '<div class="runs-empty detail">Run not found.</div>';
    return;
  }
  const active = ACTIVE.has(run.status);
  const caps = _capabilities(run);
  const children = (run.children || []).map(child => `
    <button class="runs-child" type="button" data-child-run-id="${_html(child.id)}">
      <span class="runs-status-dot runs-status-${_html(child.status)}"></span>
      <span>${_html(child.title || 'Subrun')}</span>
      <small>${_html(_statusLabel(child.status))}</small>
    </button>
  `).join('');
  const artifacts = (run.artifacts || []).map(a => `
    <a class="runs-artifact" href="${_html(a.uri || '#')}" ${a.uri ? 'target="_blank" rel="noopener noreferrer"' : ''}>
      <span>${_html(a.name)}</span>
      <small>${_html(a.artifact_type || 'artifact')}</small>
    </a>
  `).join('');
  detail.innerHTML = `
    <div class="runs-detail-head">
      <div>
        <div class="runs-kicker">${_html(_typeLabel(run.run_type))} · ${_html(_statusLabel(run.status))}</div>
        <h3>${_html(run.title || 'Untitled run')}</h3>
      </div>
      <div class="runs-actions">
        ${active && caps.pause && run.status !== 'paused' ? '<button type="button" class="runs-action" id="runs-pause">Pause</button>' : ''}
        ${active && caps.cancel ? '<button type="button" class="runs-action danger" id="runs-cancel">Cancel</button>' : ''}
        ${caps.resume && (run.status === 'paused' || run.status === 'blocked' || run.status === 'waiting_for_approval') ? '<button type="button" class="runs-action primary" id="runs-resume">Resume</button>' : ''}
      </div>
    </div>
    ${run.objective ? `<p class="runs-objective">${_html(run.objective)}</p>` : ''}
    <div class="runs-facts">
      <span>${_html(run.executor || 'executor')}</span>
      ${run.model ? `<span>${_html(run.model)}</span>` : ''}
      ${run.session_id ? `<span>session ${_html(run.session_id.slice(0, 8))}</span>` : ''}
    </div>
    <div class="runs-capabilities">
      ${caps.durability ? `<span>${_html(String(caps.durability).replace(/_/g, ' '))}</span>` : ''}
      ${caps.restart_recovery ? `<span>restart: ${_html(String(caps.restart_recovery).replace(/_/g, ' '))}</span>` : ''}
      ${run.metadata?.autonomy ? `<span>${_html(String(run.metadata.autonomy).replace(/_/g, ' '))}</span>` : '<span>review gated</span>'}
    </div>
    ${run.current_step ? `<div class="runs-current">${_html(run.current_step)}</div>` : ''}
    ${run.summary ? `<div class="runs-summary">${_html(run.summary)}</div>` : ''}
    ${run.error ? `<div class="runs-error">${_html(run.error)}</div>` : ''}
    ${artifacts ? `<div class="runs-artifacts">${artifacts}</div>` : ''}
    ${children ? `<div class="runs-children"><h4>Subruns</h4>${children}</div>` : ''}
    ${caps.inputs && active ? `
      <form class="runs-input-form" id="runs-input-form">
        <textarea id="runs-input" rows="2" placeholder="Queue a follow-up"></textarea>
        <button type="submit" class="runs-action primary">Queue</button>
      </form>
    ` : ''}
    ${caps.subruns && active ? `
      <form class="runs-subrun-form" id="runs-subrun-form">
        <input id="runs-subrun-title" type="text" placeholder="Subrun title">
        <button type="submit" class="runs-action">Spawn subrun</button>
      </form>
    ` : ''}
    <div class="runs-timeline">${(run.events || []).map(_eventMarkup).join('') || '<div class="runs-empty detail">No events yet.</div>'}</div>
  `;
  if (active) {
    _connectRunStream(run.id);
  } else if (_detailStreamId === run.id) {
    _closeRunStream();
  }
  detail.querySelectorAll('[data-child-run-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      _selectedId = btn.dataset.childRunId;
      _renderList();
      _renderDetail();
    });
  });
  document.getElementById('runs-cancel')?.addEventListener('click', () => _postRunAction(run.id, 'cancel'));
  document.getElementById('runs-pause')?.addEventListener('click', () => _postRunAction(run.id, 'pause'));
  document.getElementById('runs-resume')?.addEventListener('click', () => _postRunAction(run.id, 'resume'));
  document.getElementById('runs-input-form')?.addEventListener('submit', e => {
    e.preventDefault();
    const content = document.getElementById('runs-input')?.value || '';
    _postRunInput(run.id, content);
  });
  document.getElementById('runs-subrun-form')?.addEventListener('submit', e => {
    e.preventDefault();
    const title = document.getElementById('runs-subrun-title')?.value || 'Subrun';
    _postSubrun(run.id, title);
  });
  detail.querySelectorAll('[data-approve]').forEach(btn => {
    btn.addEventListener('click', () => _postApproval(run.id, btn.dataset.approve, true));
  });
  detail.querySelectorAll('[data-reject]').forEach(btn => {
    btn.addEventListener('click', () => _postApproval(run.id, btn.dataset.reject, false));
  });
}

async function _postRunInput(runId, content) {
  const trimmed = String(content || '').trim();
  if (!trimmed) return;
  const res = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}/inputs`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: trimmed, input_type: 'user' }),
  });
  if (!res.ok) uiModule.showToast?.('Could not queue follow-up', { error: true });
  await refreshRuns();
}

async function _postSubrun(runId, title) {
  const res = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}/subruns`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, objective: title, executor: 'sandbox_agent' }),
  });
  if (!res.ok) uiModule.showToast?.('Could not spawn subrun', { error: true });
  const data = res.ok ? await res.json() : null;
  if (data?.run?.id) _selectedId = data.run.id;
  await refreshRuns();
}

async function _postRunAction(runId, action) {
  const res = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}/${action}`, {
    method: 'POST',
    credentials: 'same-origin',
  });
  if (!res.ok) uiModule.showToast?.(`${action} failed`, { error: true });
  await refreshRuns();
}

async function _postApproval(runId, approvalId, approved) {
  const res = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}/approvals/${encodeURIComponent(approvalId)}/${approved ? 'approve' : 'reject'}`, {
    method: 'POST',
    credentials: 'same-origin',
  });
  if (!res.ok) uiModule.showToast?.('Approval update failed', { error: true });
  await refreshRuns();
}

async function _sendCurrentChatBackground() {
  const sid = sessionModule?.getCurrentSessionId?.();
  if (!sid) {
    uiModule.showToast?.('Open a chat first', { error: true });
    return;
  }
  if (chatModule?.hasActiveStream?.(sid)) {
    chatModule.detachCurrentStream?.(sid);
    uiModule.showToast?.('Running in background');
    openRuns();
    return;
  }
  const titleEl = document.getElementById('current-session-title');
  const title = titleEl?.textContent?.trim() || 'Background agent run';
  const res = await fetch(`${API_BASE}/api/runs/chat/${encodeURIComponent(sid)}/send-to-background`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, objective: `Continue chat session ${sid} in the background` }),
  });
  if (!res.ok) {
    uiModule.showToast?.('Could not register background run', { error: true });
    return;
  }
  const data = await res.json();
  _selectedId = data.run?.id || _selectedId;
  uiModule.showToast?.('Background run registered');
  openRuns(_selectedId);
}

export async function refreshRuns() {
  try {
    await _fetchRuns();
    if (_open) {
      _renderList();
      await _renderDetail();
    }
  } catch (e) {
    console.warn('Runs refresh failed:', e);
  }
}

export function openRuns(focusId) {
  if (focusId) _selectedId = focusId;
  if (_open) {
    refreshRuns();
    return;
  }
  _open = true;
  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.id = 'runs-modal';
  modal.innerHTML = `
    <div class="modal-content runs-modal-content">
      <div class="modal-header">
        <h4><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:6px"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/><path d="M5 6H2V3"/></svg>Runs</h4>
        <span style="flex:1"></span>
        <button class="close-btn" id="runs-close" aria-label="Close runs">✖</button>
      </div>
      <div class="runs-modal-body">
        <div class="runs-pane">
          <div class="runs-toolbar">
            <div class="runs-segment">
              <button type="button" class="${_filter === 'active' ? 'active' : ''}" data-runs-filter="active">Active</button>
              <button type="button" class="${_filter === 'all' ? 'active' : ''}" data-runs-filter="all">All</button>
            </div>
            <button type="button" class="runs-icon-action" id="runs-refresh" title="Refresh" aria-label="Refresh runs">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
            </button>
          </div>
          <div id="runs-list" class="runs-list"><div class="runs-empty">Loading…</div></div>
        </div>
        <div id="runs-detail" class="runs-detail"><div class="runs-empty detail">Loading…</div></div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  const content = modal.querySelector('.modal-content');
  const header = modal.querySelector('.modal-header');
  if (content && header) makeWindowDraggable(modal, { content, header });

  document.getElementById('runs-close')?.addEventListener('click', closeRuns);
  document.getElementById('runs-refresh')?.addEventListener('click', refreshRuns);
  modal.querySelectorAll('[data-runs-filter]').forEach(btn => {
    btn.addEventListener('click', async () => {
      _filter = btn.dataset.runsFilter || 'active';
      _selectedId = null;
      modal.querySelectorAll('[data-runs-filter]').forEach(b => b.classList.toggle('active', b === btn));
      await refreshRuns();
    });
  });
  modal.addEventListener('click', e => {
    if (uiModule.isTouchInsideModal?.()) return;
    if (e.target === modal) closeRuns();
  });
  _escHandler = e => {
    if (e.key === 'Escape') closeRuns();
  };
  document.addEventListener('keydown', _escHandler);
  refreshRuns();
}

export function closeRuns() {
  if (!_open) return;
  _open = false;
  _closeRunStream();
  const modal = document.getElementById('runs-modal');
  if (modal) {
    const content = modal.querySelector('.modal-content');
    if (content) {
      content.classList.add('modal-closing');
      content.addEventListener('animationend', () => modal.remove(), { once: true });
      setTimeout(() => { if (modal.parentElement) modal.remove(); }, 250);
    } else {
      modal.remove();
    }
  }
  if (_escHandler) {
    document.removeEventListener('keydown', _escHandler);
    _escHandler = null;
  }
}

export function isRunsOpen() {
  return _open;
}

export function init(apiBase, sessions, chat) {
  API_BASE = apiBase || API_BASE;
  sessionModule = sessions || sessionModule;
  chatModule = chat || chatModule;
  document.getElementById('run-background-btn')?.addEventListener('click', _sendCurrentChatBackground);
  refreshRuns();
  if (!_poll) _poll = setInterval(refreshRuns, 15000);
}

const runsModule = { init, openRuns, closeRuns, isRunsOpen, refreshRuns };
export default runsModule;
window.runsModule = runsModule;
