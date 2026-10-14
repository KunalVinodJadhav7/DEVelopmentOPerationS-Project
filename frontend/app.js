const state = {
    token: localStorage.getItem('leave_token') || '',
    user: null,
    requests: [],
    leaveTypes: [],
    balances: [],
    policies: [],
    page: 'overview',
    selected: null
};

const roleMeta = {
    employee: {
        label: 'Employee',
        tier: 1,
        home: 'employee',
        nav: [
            ['overview', 'Overview', '⌂'],
            ['employee', 'Apply for leave', '＋'],
            ['requests', 'My requests', '▣'],
            ['audit', 'Audit trail', '◌']
        ]
    },

    hr: {
        label: 'HR',
        tier: 2,
        home: 'hr',
        nav: [
            ['overview', 'Overview', '⌂'],
            ['requests', 'HR review queue', '☰'],
            ['audit', 'Audit trail', '◌']
        ]
    },

    manager: {
        label: 'Manager',
        tier: 3,
        home: 'manager',
        nav: [
            ['overview', 'Overview', '⌂'],
            ['requests', 'Manager queue', '☰'],
            ['audit', 'Audit trail', '◌']
        ]
    },

    admin: {
        label: 'Admin',
        tier: 4,
        home: 'admin',
        nav: [
            ['overview', 'Overview', '⌂'],
            ['requests', 'Admin queue', '☰'],
            ['policies', 'Leave policies', '⚙'],
            ['audit', 'Audit trail', '◌']
        ]
    },

    super_admin: {
        label: 'Super Admin',
        tier: 5,
        home: 'super-admin',
        nav: [
            ['overview', 'Overview', '⌂'],
            ['requests', 'Operations', '☰'],
            ['policies', 'Leave policies', '⚙'],
            ['audit', 'Audit trail', '◌']
        ]
    }
};

const roleLabel = r => roleMeta[r]?.label || r;

const $ = s => document.querySelector(s);

const escapeHtml = v =>
    String(v ?? '').replace(
        /[&<>"']/g,
        c => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[c])
    );

function authHeaders() {
    return state.token
        ? { Authorization: `Bearer ${state.token}` }
        : {};
}

async function api(url, opt = {}) {
    const res = await fetch(url, {
        ...opt,
        headers: {
            ...(opt.headers || {}),
            ...authHeaders()
        }
    });

    const text = await res.text();

    let body = {};

    try {
        body = text ? JSON.parse(text) : {};
    } catch {
        body = { detail: text };
    }

    if (!res.ok) {
        if (res.status === 401) {
            logout(false);
        }

        throw new Error(body.detail || 'Request failed');
    }

    return body;
}

function toast(msg, ok = false) {
    const el = $('#toast');

    if (!el) return;

    el.textContent = msg;
    el.className = `toast ${ok ? 'ok' : ''}`;
    el.classList.remove('hidden');

    setTimeout(() => {
        el.classList.add('hidden');
    }, 2400);
}

function statusLabel(s) {
    return String(s || '')
        .replaceAll('_', ' ')
        .replace(/\b\w/g, x => x.toUpperCase());
}

function progressFor(status) {
    return {
        PENDING_HR: 20, // legacy status only
        PENDING_MANAGER: 20,
        PENDING_HR_FINAL: 40,
        PENDING_ADMIN: 60,
        APPROVED: 100,
        REJECTED: 100
    }[status] || 0;
}

function timeline(status) {
    const steps = [
        ['Employee', 'Submitted'],
        ['Manager', 'Approve or reject'],
        ['HR', 'Final review'],
        ['Admin', 'Finalized'],
        ['Super Admin', 'Notified']
    ];

    const order = {
        PENDING_HR: 2, // legacy status during upgrade only
        PENDING_MANAGER: 1,
        PENDING_HR_FINAL: 2,
        PENDING_ADMIN: 3,
        APPROVED: 4,
        REJECTED: 4
    };

    const idx = order[status] ?? 0;

    return `
    <div class="timeline">
      ${steps
            .map((s, i) => {
                let cls = i < idx
                    ? 'complete'
                    : i === idx
                        ? 'current'
                        : '';

                if (status === 'REJECTED' && i === idx) {
                    cls = 'rejected';
                }

                return `
            <div class="step ${cls}">
              <div class="dot">${i < idx ? '✓' : i + 1}</div>
              <span>
                ${s[0]}<br>
                ${s[1]}
              </span>
            </div>
          `;
            })
            .join('')}
    </div>
  `;
}

function requestCard(r, actions = '') {
    return `
    <article class="request">
      <div>
        <div class="request-title">
          Leave #${r.id}
          ${r.employee_id != null
            ? `· Employee #${r.employee_id}`
            : ''}
        </div>

        <div class="request-meta">
          ${escapeHtml(r.start_date || '')}
          →
          ${escapeHtml(r.end_date || '')}
          · ${escapeHtml(r.leave_type_code || 'CL')}
          · ${Number(r.requested_days || 0)} workday(s)
          ·
          ${escapeHtml(r.reason || '')}
          ${r.manager_approved === true ? ' · Manager decision: Approved' : r.manager_approved === false ? ' · Manager decision: Rejected' : ''}
        </div>
      </div>

      <span class="status ${r.status}">
        ${statusLabel(r.status)}
      </span>

      <div class="queue-actions">
        <button
          class="btn soft"
          onclick="viewRequest(${r.id})"
        >
          View
        </button>

        ${actions}
      </div>
    </article>
  `;
}

function shell() {
    document.body.innerHTML = `
    <div id="toast" class="toast hidden"></div>

    <div class="app">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-mark">LF</div>

          <div>
            <strong>LeaveFlow</strong>
            <span>Enterprise Leave</span>
          </div>
        </div>

        <nav class="nav" id="nav"></nav>

        <div class="side-bottom">
          <div class="user-card">
            <strong id="userName"></strong>
            <span id="userRole"></span>
          </div>

          <button class="logout" id="logout">
            Sign out
          </button>
        </div>
      </aside>

      <main class="main">
        <div class="topbar">
          <div class="title">
            <div class="eyebrow" id="tier"></div>
            <h1 id="title"></h1>
            <p id="subtitle"></p>
          </div>

          <div class="top-actions">
            <button class="btn" id="refresh">
              ↻ Refresh
            </button>
          </div>
        </div>

        <div id="content"></div>
      </main>
    </div>

    <div id="modalRoot"></div>
  `;

    $('#logout').onclick = () => logout(true);
    $('#refresh').onclick = loadRequests;
}

function buildNav() {
    const meta = roleMeta[state.user.role];

    $('#nav').innerHTML = meta.nav
        .map(
            n => `
        <button
          class="${state.page === n[0] ? 'active' : ''}"
          onclick="navigate('${n[0]}')"
        >
          <span class="icon">${n[2]}</span>
          <span>${n[1]}</span>
        </button>
      `
        )
        .join('');

    $('#userName').textContent = state.user.username;
    $('#userRole').textContent = meta.label;
}

function headers(page) {
    const meta = roleMeta[state.user.role];

    const map = {
        overview: [
            'Overview',
            `Your ${meta.label.toLowerCase()} workspace`
        ],

        employee: [
            'Apply for leave',
            'Submit a request and follow every approval step'
        ],

        requests: [
            meta.label === 'Employee'
                ? 'My requests'
                : `${meta.label} review queue`,
            'Focus on the requests that need your action'
        ],

        audit: [
            'Audit trail',
            'Trace every decision and notification'
        ],

        policies: [
            'Leave policies',
            'Configure leave types and annual weekday allowances'
        ]
    };

    const h = map[page] || map.overview;

    $('#tier').textContent =
        `Tier ${meta.tier} · ${meta.label}`;

    $('#title').textContent = h[0];
    $('#subtitle').textContent = h[1];
}

function navigate(page) {
    state.page = page;

    buildNav();
    headers(page);
    render();
}

function stats() {
    const all = state.requests;

    const counts = {
        pending: all.filter(
            r => r.status.startsWith('PENDING')
        ).length,

        approved: all.filter(
            r => r.status === 'APPROVED'
        ).length,

        rejected: all.filter(
            r => r.status === 'REJECTED'
        ).length
    };

    return `
    <div class="grid stats">

      <div class="card stat">
        <div class="stat-label">
          Open workflow items
        </div>

        <div class="stat-value">
          ${counts.pending}
        </div>

        <div class="stat-foot">
          Requests still moving through approval
        </div>
      </div>

      <div class="card stat">
        <div class="stat-label">
          Approved
        </div>

        <div class="stat-value">
          ${counts.approved}
        </div>

        <div class="stat-foot">
          Final decisions granted
        </div>
      </div>

      <div class="card stat">
        <div class="stat-label">
          Rejected
        </div>

        <div class="stat-value">
          ${counts.rejected}
        </div>

        <div class="stat-foot">
          Final decisions declined
        </div>
      </div>

      <div class="card stat">
        <div class="stat-label">
          Total requests
        </div>

        <div class="stat-value">
          ${all.length}
        </div>

        <div class="stat-foot">
          Visible to your role
        </div>
      </div>

    </div>
  `;
}

function nextPanel() {
    const r = state.user.role;

    const target = {
        employee: 'PENDING_MANAGER',
        hr: 'PENDING_HR_FINAL',
        manager: 'PENDING_MANAGER',
        admin: 'PENDING_ADMIN',
        super_admin: 'APPROVED'
    }[r];

    const n = state.requests.find(x => x.status === target);

    let title = 'You are all caught up';
    let body = 'There is nothing waiting for your action right now.';

    if (n) {
        title = `Leave #${n.id} needs your attention`;

        body =
            r === 'employee'
                ? 'Track the request as it moves through the approval flow.'
                : 'Open the request, review the details, and record your decision.';
    }

    return `
    <section class="card section">

      <div class="section-head">
        <div>
          <div class="eyebrow">Next action</div>

          <h2>${title}</h2>

          <p>${body}</p>
        </div>
      </div>

      ${n
            ? `
            <div class="next-action">

              <div class="request-title">
                ${escapeHtml(n.reason)}
              </div>

              <div class="request-meta">
                ${escapeHtml(n.start_date)}
                →
                ${escapeHtml(n.end_date)}
              </div>

              <div style="margin-top:14px">
                ${timeline(n.status)}
              </div>

              <div class="progress-wrap">
                <div class="progress-row">
                  <span>Approval progress</span>
                  <strong>${progressFor(n.status)}%</strong>
                </div>

                <div class="progress">
                  <div
                    style="width:${progressFor(n.status)}%"
                  ></div>
                </div>
              </div>

              <div style="margin-top:16px">
                <button
                  class="btn primary"
                  onclick="viewRequest(${n.id})"
                >
                  Open request
                </button>
              </div>

            </div>
          `
            : ''
        }

    </section>
  `;
}

function recentPanel() {
    return `
    <section class="card section">

      <div class="section-head">
        <div>
          <div class="eyebrow">Activity</div>
          <h2>Recent requests</h2>
        </div>

        <button
          class="btn"
          onclick="navigate('requests')"
        >
          View all
        </button>
      </div>

      <div class="request-list">
        ${state.requests
            .slice(0, 4)
            .map(r => requestCard(r))
            .join('') ||
        '<div class="empty">No leave requests yet.</div>'
        }
      </div>

    </section>
  `;
}

function employeePage() {
    return `
    <div class="grid two">

      <section class="card section">

        <div class="section-head">
          <div>
            <div class="eyebrow">New request</div>
            <h2>Apply for leave</h2>
            <p>
              Start your request here.
              Choose a leave type. Weekdays (Monday-Friday) are counted; public holidays are not excluded. The Manager decides first, and HR then performs a separate final review.
            </p>
          </div>
        </div>

        <form id="leaveForm" class="form-grid">

          <div class="field wide">
            <label>Leave type</label>
            <select name="leave_type_code" id="leaveTypeSelect" required>
              ${state.leaveTypes.map(t => `<option value="${escapeHtml(t.code)}" ${t.code === 'CL' ? 'selected' : ''}>${escapeHtml(t.code)} — ${escapeHtml(t.name)} (${Number(t.annual_allowance)} days/year)</option>`).join('')}
            </select>
            <div class="hint" id="leaveTypeBalance"></div>
          </div>

          <div class="field">
            <label>Start date</label>
            <input
              name="start_date"
              type="date"
              required
            >
          </div>

          <div class="field">
            <label>End date</label>
            <input
              name="end_date"
              type="date"
              required
            >
          </div>

          <div class="field wide">
            <label>Reason</label>

            <textarea
              name="reason"
              minlength="5"
              maxlength="250"
              required
              placeholder="Briefly explain why you need leave"
            ></textarea>
          </div>

          <div class="field wide">
            <label>
              Supporting document
              <span class="hint">
                optional · max 5 MB
              </span>
            </label>

            <input
              name="supporting_document"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
            >
          </div>

          <div class="wide">
            <button
              class="btn primary"
              type="submit"
            >
              Submit leave request
            </button>
          </div>

        </form>

        <div id="leaveAlert"></div>

      </section>

      <section class="card section">

        <div class="eyebrow">
          How it works
        </div>

        <h2>Your approval path</h2>

        <p>
          Every request goes to the Manager first. The Manager decides based on workload, staffing, and team priorities. HR then reviews: only a Manager approval can be vetoed, and only for a policy violation, insufficient leave balance, or legal/compliance issue. Every veto needs a category and specific reason; a Manager rejection remains rejected.
        </p>

        ${timeline('PENDING_MANAGER')}

        <div class="progress-wrap">

          <div class="progress-row">
            <span>Starts here</span>
            <strong>20%</strong>
          </div>

          <div class="progress">
            <div style="width:20%"></div>
          </div>

        </div>

      </section>

    </div>

    <section class="card section balance-section">
      <div class="section-head">
        <div>
          <div class="eyebrow">Annual entitlement</div>
          <h2>My leave balances · ${new Date().getFullYear()}</h2>
          <p>Pending requests reserve days until they are rejected. Weekdays are counted; public holidays are not excluded.</p>
        </div>
      </div>
      <div class="balance-grid">
        ${state.balances.filter(b => b.enabled).map(b => `
          <article class="balance-card">
            <div class="balance-code">${escapeHtml(b.code)}</div>
            <div class="balance-name">${escapeHtml(b.name)}</div>
            <div class="balance-number">${Number(b.remaining_days)} <span>remaining</span></div>
            <div class="balance-foot">${Number(b.used_or_reserved_days)} used/reserved of ${Number(b.annual_allowance)} workday(s)</div>
          </article>
        `).join('') || '<div class="empty">No enabled leave types available.</div>'}
      </div>
    </section>
  `;
}

function canRoleReviewRequest(role, request) {
    if (role === 'employee') return true;
    if (role === 'hr') return request.status === 'PENDING_HR_FINAL';
    if (role === 'manager') return request.status === 'PENDING_MANAGER';
    if (role === 'admin') return request.status === 'PENDING_ADMIN';
    if (role === 'super_admin') return true;
    return false;
}

function queuePage() {
    const role = state.user.role;
    const filters = state.requests;
    const relevant = filters.filter(r => canRoleReviewRequest(role, r));

    return `
    <section class="card section">

      <div class="section-head">

        <div>
          <div class="eyebrow">Queue</div>

          <h2>
            ${role === 'employee'
            ? 'All my requests'
            : relevant.length
                ? `${relevant.length} request${relevant.length === 1 ? '' : 's'
                } waiting`
                : 'No requests waiting'
        }
          </h2>
        </div>

        <div class="search-row">

          <input
            id="search"
            placeholder="Search by ID or reason"
          >

          <select id="filter">
            <option value="all">
              All statuses
            </option>

            <option value="PENDING_MANAGER">
              Pending Manager
            </option>

            <option value="PENDING_HR_FINAL">
              Pending HR final review
            </option>

            <option value="PENDING_ADMIN">
              Pending Admin
            </option>

            <option value="APPROVED">
              Approved
            </option>

            <option value="REJECTED">
              Rejected
            </option>
          </select>

        </div>

      </div>

      <div id="requestList" class="request-list"></div>

    </section>
  `;
}

function auditPage() {
    return `
    <section class="card section">

      <div class="section-head">

        <div>
          <div class="eyebrow">Traceability</div>

          <h2>Audit trail</h2>

          <p>
            Select a request to see every action taken.
          </p>
        </div>

      </div>

      <div class="request-list">

        ${state.requests
            .slice(0, 12)
            .map(r => requestCard(r))
            .join('') ||
        '<div class="empty">No requests available.</div>'
        }

      </div>

    </section>
  `;
}

function render() {
    if (!state.user) return;

    headers(state.page);

    if (state.page === 'overview') {
        $('#content').innerHTML =
            stats() +
            `
        <div class="grid two">
          ${nextPanel()}
          ${recentPanel()}
        </div>
      `;

        return;
    }

    if (state.page === 'employee') {
        $('#content').innerHTML = employeePage();
        $('#leaveForm').onsubmit = submitLeave;
        const typeSelect = $('#leaveTypeSelect');
        if (typeSelect) {
            typeSelect.onchange = updateLeaveTypeBalance;
            updateLeaveTypeBalance();
        }
        return;
    }

    if (state.page === 'policies') {
        $('#content').innerHTML = policiesPage();
        $('#policyCreateForm').onsubmit = createLeavePolicy;
        document.querySelectorAll('.policy-save').forEach(button => {
            button.onclick = () => saveLeavePolicy(button.dataset.code);
        });
        return;
    }

    if (state.page === 'requests') {
        $('#content').innerHTML = queuePage();

        renderRequestList();

        return;
    }

    if (state.page === 'audit') {
        $('#content').innerHTML = auditPage();

        return;
    }
}

function renderRequestList() {
    const box = $('#requestList');

    if (!box) return;

    const search =
        ($('#search')?.value || '').toLowerCase();

    const filter =
        $('#filter')?.value || 'all';

    let rows = state.requests.filter(
        r =>
            (filter === 'all' || r.status === filter) &&
            `${r.id} ${r.reason}`
                .toLowerCase()
                .includes(search)
    );

    rows = rows.filter(r => canRoleReviewRequest(state.user.role, r));

    box.innerHTML = rows.length
        ? rows
            .map(r => {
                let action = '';

                if (
                    state.user.role === 'hr' &&
                    r.status === 'PENDING_HR_FINAL'
                ) {
                    action = `
              <button
                class="btn primary"
                onclick="openReview(${r.id}, 'hr-final')"
              >
                Review
              </button>
            `;
                }

                if (
                    state.user.role === 'manager' &&
                    r.status === 'PENDING_MANAGER'
                ) {
                    action = `
              <button
                class="btn primary"
                onclick="openReview(${r.id}, 'manager')"
              >
                Review
              </button>
            `;
                }

                if (
                    state.user.role === 'admin' &&
                    r.status === 'PENDING_ADMIN'
                ) {
                    action = `
              <button
                class="btn primary"
                onclick="openReview(${r.id}, 'admin')"
              >
                Finalize
              </button>
            `;
                }

                if (
                    state.user.role === 'super_admin' &&
                    ['APPROVED', 'REJECTED'].includes(r.status)
                ) {
                    action = `
              <button
                class="btn primary"
                onclick="notifyEmployee(${r.id})"
              >
                Notify
              </button>
            `;
                }

                return requestCard(r, action);
            })
            .join('')
        : '<div class="empty">No matching requests.</div>';

    if ($('#search')) {
        $('#search').oninput = renderRequestList;
        $('#filter').onchange = renderRequestList;
    }
}

async function loadRequests() {
    try {
        const [requests, leaveTypes, balanceResponse] = await Promise.all([
            api('/api/leave/requests'),
            api('/api/leave/types'),
            api('/api/leave/balances')
        ]);
        state.requests = requests;
        state.leaveTypes = leaveTypes;
        state.balances = balanceResponse.balances || [];
        if (['admin', 'super_admin'].includes(state.user?.role)) {
            state.policies = await api('/api/admin/leave-policies');
        }
        render();
    } catch (e) {
        toast(e.message);
    }
}

function updateLeaveTypeBalance() {
    const selectedCode = $('#leaveTypeSelect')?.value;
    const policy = state.leaveTypes.find(type => type.code === selectedCode);
    const balance = state.balances.find(item => item.code === selectedCode);
    const target = $('#leaveTypeBalance');
    if (!target || !policy) return;
    target.textContent = balance
        ? `${balance.remaining_days} of ${balance.annual_allowance} workday(s) remaining for ${balance.year}; ${balance.used_or_reserved_days} used or reserved.`
        : `${policy.annual_allowance} workday(s) per calendar year.`;
}

function policiesPage() {
    const rows = state.policies.map(policy => `
      <div class="policy-row">
        <div class="policy-code">${escapeHtml(policy.code)}</div>
        <div class="field">
          <label for="policy-name-${escapeHtml(policy.code)}">Name</label>
          <input id="policy-name-${escapeHtml(policy.code)}" value="${escapeHtml(policy.name)}" maxlength="80" required>
        </div>
        <div class="field">
          <label for="policy-days-${escapeHtml(policy.code)}">Annual workdays</label>
          <input id="policy-days-${escapeHtml(policy.code)}" type="number" min="0" max="260" value="${Number(policy.annual_allowance)}" required>
        </div>
        <label class="policy-enabled"><input id="policy-enabled-${escapeHtml(policy.code)}" type="checkbox" ${policy.enabled ? 'checked' : ''}> Enabled</label>
        <button type="button" class="btn primary policy-save" data-code="${escapeHtml(policy.code)}">Save</button>
      </div>
    `).join('');
    return `
      <div class="grid policies-layout">
        <section class="card section">
          <div class="section-head"><div><div class="eyebrow">Policy setup</div><h2>Add a leave type</h2><p>Codes are immutable after creation. Disabled types remain available for historical requests.</p></div></div>
          <form id="policyCreateForm" class="form-grid">
            <div class="field"><label for="new-policy-code">Code</label><input id="new-policy-code" name="code" minlength="2" maxlength="10" pattern="[A-Za-z][A-Za-z0-9_]{1,9}" placeholder="SL" required></div>
            <div class="field"><label for="new-policy-name">Name</label><input id="new-policy-name" name="name" minlength="2" maxlength="80" placeholder="Sick Leave" required></div>
            <div class="field"><label for="new-policy-days">Annual workdays</label><input id="new-policy-days" name="annual_allowance" type="number" min="0" max="260" value="10" required></div>
            <label class="policy-enabled"><input name="enabled" type="checkbox" checked> Enabled for new requests</label>
            <div class="wide"><button class="btn primary" type="submit">Create leave type</button></div>
          </form>
        </section>
        <section class="card section">
          <div class="section-head"><div><div class="eyebrow">Annual entitlement</div><h2>Existing leave types</h2><p>Weekdays, Monday-Friday, are counted. Public holidays are not excluded.</p></div></div>
          <div class="policy-list">${rows || '<div class="empty">No leave types configured.</div>'}</div>
        </section>
      </div>
    `;
}

async function createLeavePolicy(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const payload = {
        code: String(values.get('code') || '').trim().toUpperCase(),
        name: String(values.get('name') || '').trim(),
        annual_allowance: Number(values.get('annual_allowance')),
        enabled: values.get('enabled') === 'on'
    };
    try {
        await api('/api/admin/leave-policies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        await loadRequests();
        toast(`Leave type ${payload.code} created`, true);
    } catch (e) {
        toast(e.message);
    }
}

async function saveLeavePolicy(code) {
    const payload = {
        name: $(`#policy-name-${code}`).value.trim(),
        annual_allowance: Number($(`#policy-days-${code}`).value),
        enabled: $(`#policy-enabled-${code}`).checked
    };
    try {
        await api(`/api/admin/leave-policies/${encodeURIComponent(code)}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        await loadRequests();
        toast(`Leave policy ${code} saved`, true);
    } catch (e) {
        toast(e.message);
    }
}

async function submitLeave(ev) {
    ev.preventDefault();

    const form = ev.currentTarget;
    const fd = new FormData(form);

    try {
        const data = await api(
            '/api/leave/submit',
            {
                method: 'POST',
                body: fd
            }
        );

        form.reset();

        // Refresh request data first.
        await loadRequests();

        // loadRequests() re-renders the employee page,
        // so set the success message afterward.
        $('#leaveAlert').innerHTML =
            '<div class="alert ok">Leave request submitted successfully.</div>';

        toast(
            `Leave #${data.id} created`,
            true
        );

    } catch (e) {
        $('#leaveAlert').innerHTML =
            `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
}

function viewRequest(id) {
    const r = state.requests.find(
        x => x.id === id
    );

    if (!r) return;

    const documentHtml = r.document_name
        ? `
      <div class="document">
        <strong>Supporting document</strong>

        <div style="margin-top:6px">
          ${escapeHtml(r.document_name)}
        </div>

        <div style="margin-top:10px">
          <a
            href="/api/leave/${r.id}/document"
            target="_blank"
          >
            Open document
          </a>
        </div>
      </div>
    `
        : '';

    $('#modalRoot').innerHTML = `
    <div
      class="modal-backdrop"
      onclick="closeModal(event)"
    >
      <div
        class="modal"
        onclick="event.stopPropagation()"
      >

        <div class="modal-head">

          <div>
            <div class="eyebrow">
              Leave request #${r.id}
            </div>

            <h2 style="margin:4px 0 0">
              ${escapeHtml(r.reason)}
            </h2>
          </div>

          <button
            class="close"
            onclick="closeModal()"
          >
            ×
          </button>

        </div>

        <div
          class="detail"
          style="margin-top:18px"
        >

          <dl class="kv">

            <dt>Employee</dt>
            <dd>#${escapeHtml(r.employee_id)}</dd>

            <dt>Start</dt>
            <dd>${escapeHtml(r.start_date)}</dd>

            <dt>End</dt>
            <dd>${escapeHtml(r.end_date)}</dd>

            <dt>Status</dt>
            <dd>
              <span class="status ${r.status}">
                ${statusLabel(r.status)}
              </span>
            </dd>

            <dt>Manager decision</dt>
            <dd>${r.manager_approved === true ? 'Approved' : r.manager_approved === false ? 'Rejected' : 'Awaiting Manager review'}</dd>

            <dt>Manager rationale</dt>
            <dd>${escapeHtml(r.manager_comments || 'Not recorded yet')}</dd>

            <dt>HR review comments</dt>
            <dd>${escapeHtml(r.hr_comments || 'Not recorded yet')}</dd>

            ${r.hr_veto_category ? `
              <dt>HR veto category</dt>
              <dd>${escapeHtml({policy_violation: 'Policy violation', insufficient_leave_balance: 'Insufficient leave balance', legal_compliance: 'Legal/compliance issue'}[r.hr_veto_category] || r.hr_veto_category)}</dd>
            ` : ''}

            <dt>Created</dt>
            <dd>${escapeHtml(r.created_at || '')}</dd>

          </dl>

          <div>
            <div class="eyebrow">
              Approval timeline
            </div>

            ${timeline(r.status)}

            <div class="progress-wrap">

              <div class="progress-row">
                <span>Progress</span>
                <strong>${progressFor(r.status)}%</strong>
              </div>

              <div class="progress">
                <div
                  style="width:${progressFor(r.status)}%"
                ></div>
              </div>

            </div>
          </div>

        </div>

        ${documentHtml}

        <div
          id="modalAudit"
          style="margin-top:18px"
        ></div>

      </div>
    </div>
  `;

    loadAudit(id);
}

async function loadAudit(id) {
    try {
        const rows = await api(
            `/api/leave/${id}/audit`,
            { cache: 'no-store' }
        );

        const box = $('#modalAudit');

        if (!box) return;

        box.innerHTML = `
      <div class="eyebrow">
        Audit
      </div>

      <div
        class="audit"
        style="margin-top:8px"
      >
        ${rows
                .map(
                    a => `
                <div class="audit-item">

                  <strong>
                    ${escapeHtml(
                        a.action_performed.replaceAll(
                            '_',
                            ' '
                        )
                    )}
                  </strong>

                  <div>
                    ${escapeHtml(
                        a.comments || ''
                    )}
                  </div>

                  <span>
                    Actor #${escapeHtml(a.actor_id)}
                    ·
                    ${escapeHtml(a.timestamp || '')}
                  </span>

                </div>
              `
                )
                .join('') ||
            '<div class="empty">No audit events yet.</div>'
            }
      </div>
    `;
    } catch (e) {
        const box = $('#modalAudit');
        if (box) {
            box.innerHTML = `<div class="eyebrow">Audit</div><div class="alert error">Unable to load audit history: ${escapeHtml(e.message)}</div>`;
        }
    }
}

function closeModal() {
    $('#modalRoot').innerHTML = '';
}

window.closeModal = closeModal;
window.viewRequest = viewRequest;
window.navigate = navigate;

function openReview(id, kind) {
    const r = state.requests.find(
        x => x.id === id
    );

    if (!r) return;

    $('#modalRoot').innerHTML = `
    <div
      class="modal-backdrop"
      onclick="closeModal(event)"
    >
      <div
        class="modal"
        onclick="event.stopPropagation()"
      >

        <div class="modal-head">

          <div>
            <div class="eyebrow">
              ${kind === 'admin'
            ? 'Final decision'
            : kind === 'hr-final'
                ? 'HR final review'
                : kind === 'manager'
                    ? 'Manager decision'
                    : 'Review'}
              · Request #${id}
            </div>

            <h2>
              ${escapeHtml(r.reason)}
            </h2>
          </div>

          <button
            class="close"
            onclick="closeModal()"
          >
            ×
          </button>

        </div>

        <p style="color:var(--muted)">
          ${escapeHtml(r.start_date)}
          →
          ${escapeHtml(r.end_date)}
          · ${escapeHtml(r.leave_type_code || 'CL')} · ${Number(r.requested_days || 0)} workday(s)
          · Employee #${escapeHtml(r.employee_id)}
        </p>

        <div
          class="field"
          style="margin-top:18px"
        >
          <label>
            Decision comments
          </label>

          <textarea
            id="reviewComments"
            maxlength="2000"
            placeholder="Add a clear decision reason"
          ></textarea>
          ${kind === 'manager' ? '<p class="hint">Decide first based on workload, staffing, and team priorities. Record a clear rationale. HR performs a separate, limited policy/compliance review afterward.</p>' : ''}
          ${kind === 'hr-final' ? (r.manager_approved === false ? '<p class="hint">The Manager rejected this request. Record a final review to confirm the rejection. HR cannot convert a Manager rejection into an approval or issue a second veto.</p>' : '<p class="hint">The Manager approved this request. Approve it for Admin review, or veto only for a policy violation, insufficient leave balance, or legal/compliance issue. A veto category and a specific reason are required.</p>') : ''}
        </div>

        ${kind === 'hr-final' && r.manager_approved === true ? `
          <div class="field" style="margin-top:12px">
            <label for="hrVetoCategory">HR veto category (required only when rejecting)</label>
            <select id="hrVetoCategory">
              <option value="">Select a permitted reason category</option>
              <option value="policy_violation">Policy violation</option>
              <option value="insufficient_leave_balance">Insufficient leave balance</option>
              <option value="legal_compliance">Legal/compliance issue</option>
            </select>
            <p class="hint">For a veto, explain the specific policy, balance, or compliance issue in Decision comments (at least 10 characters).</p>
          </div>
        ` : ''}

        <div id="reviewAlert"></div>

        <div
          style="
            display:flex;
            gap:10px;
            justify-content:flex-end;
            margin-top:16px
          "
        >
          ${kind === 'hr-final' && r.manager_approved === false ? '' : `
            <button
              class="btn danger"
              onclick="submitReview(${id}, '${kind}', false)"
            >
              Reject
            </button>
          `}

          <button
            class="btn primary"
            onclick="submitReview(${id}, '${kind}', true)"
          >
            ${kind === 'hr-final' && r.manager_approved === false ? 'Confirm rejection' : kind === 'hr-final' ? 'Confirm for Admin' : 'Approve'}
          </button>
        </div>

      </div>
    </div>
  `;
}

async function submitReview(
    id,
    kind,
    approved
) {
    const comments = $('#reviewComments').value.trim();

    if (!comments) {
        $('#reviewAlert').innerHTML =
            '<div class="alert error">Please enter comments before deciding.</div>';
        return;
    }

    const request = state.requests.find(x => x.id === id);
    const isHrVeto = kind === 'hr-final'
        && request?.manager_approved === true
        && approved === false;
    let vetoCategory = null;

    if (isHrVeto) {
        vetoCategory = $('#hrVetoCategory')?.value || '';
        if (!vetoCategory) {
            $('#reviewAlert').innerHTML =
                '<div class="alert error">Select a permitted HR veto category.</div>';
            return;
        }
        if (comments.length < 10) {
            $('#reviewAlert').innerHTML =
                '<div class="alert error">Provide a specific HR veto reason of at least 10 characters.</div>';
            return;
        }
    }

    const endpoint = {
        hr: `/api/leave/${id}/hr-review`,
        'hr-final': `/api/leave/${id}/hr-review`,
        manager: `/api/leave/${id}/manager-approve`,
        admin: `/api/leave/${id}/admin-finalize`
    }[kind];

    const payload = { approved, comments };
    if (isHrVeto) payload.veto_category = vetoCategory;

    try {
        const result = await api(endpoint, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        closeModal();
        await loadRequests();

        toast(
            kind === 'manager'
                ? `Manager ${approved ? 'approval' : 'rejection'} recorded; HR review is next`
                : result.action === 'HR_VETOED_MANAGER_APPROVAL'
                    ? 'Request rejected — HR veto recorded'
                    : approved && kind === 'hr-final' && request?.manager_approved === false
                        ? 'Manager rejection confirmed; request remains rejected'
                        : approved
                            ? 'Decision recorded'
                            : 'Request rejected',
            true
        );
    } catch (e) {
        $('#reviewAlert').innerHTML =
            `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
}


async function notifyEmployee(id) {
    try {
        await api(
            `/api/leave/${id}/notify-employee`,
            {
                method: 'POST'
            }
        );

        await loadRequests();

        toast(
            `Employee notified for leave #${id}`,
            true
        );

    } catch (e) {
        toast(e.message);
    }
}

window.openReview = openReview;
window.submitReview = submitReview;
window.notifyEmployee = notifyEmployee;

async function bootstrap() {
    if (!state.token) {
        location.href = '/dashboard';
        return;
    }

    try {
        state.user =
            await api('/api/auth/me');

        const pathPage = {
            '/employee': 'employee',
            '/hr': 'requests',
            '/manager': 'requests',
            '/admin': 'requests',
            '/super-admin': 'requests',
            '/dashboard': 'overview'
        }[location.pathname] || 'overview';

        if (
            state.user.role === 'employee' &&
            [
                '/hr',
                '/manager',
                '/admin',
                '/super-admin'
            ].includes(location.pathname)
        ) {
            location.href = '/employee';
        }

        if (
            state.user.role !== 'employee' &&
            location.pathname === '/employee'
        ) {
            location.href =
                '/' +
                state.user.role.replace('_', '-');
        }

        state.page = pathPage;

        shell();
        buildNav();

        await loadRequests();

    } catch (e) {
        logout(false);
    }
}

function logout(go = true) {
    state.token = '';
    state.user = null;

    localStorage.removeItem('leave_token');

    if (go) {
        location.href = '/dashboard';
    }
}

document.addEventListener(
    'DOMContentLoaded',
    bootstrap
);
