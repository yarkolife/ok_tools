/* =========================================================
   rental/static/rental/js/shared.jsx
   Shared utilities, primitives, CSRF helper.
   Exposes helpers on window so other scripts can use them.
   ========================================================= */

/* --------- tiny helpers --------- */
function cls(...xs) { return xs.filter(Boolean).join(' '); }

function fmtDate(s) {
  if (!s) return '—';
  const d = new Date(typeof s === 'string' ? s.replace(' ', 'T') : s);
  if (isNaN(d)) return s;
  return d.toLocaleDateString('de-DE',
                              { day: '2-digit', month: '2-digit', year: 'numeric' }) +
         ', ' + d.toLocaleTimeString('de-DE',
                                     { hour: '2-digit', minute: '2-digit' });
}

function fmtDateShort(s) {
  if (!s) return '—';
  const d = new Date(typeof s === 'string' ? s.replace(' ', 'T') : s);
  if (isNaN(d)) return s;
  return d.toLocaleDateString('de-DE',
                              { day: '2-digit', month: '2-digit' }) +
         ' · ' + d.toLocaleTimeString('de-DE',
                                      { hour: '2-digit', minute: '2-digit' });
}

/* --------- CSRF --------- */
function getCookie(name) {
  const v = `; ${document.cookie}`.split(`; ${name}=`);
  if (v.length === 2) return v.pop().split(';').shift();
  return '';
}

async function apiPost(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) {
    let msg = `${url} → ${r.status}`;
    try { const b = await r.clone().json(); if (b && b.error) msg = b.error; } catch {}
    throw new Error(msg);
  }
  return r.json();
}

async function apiGet(url) {
  const r = await fetch(url, { credentials: 'same-origin' });
  if (!r.ok) {
    let msg = `${url} → ${r.status}`;
    try { const b = await r.clone().json(); if (b && b.error) msg = b.error; } catch {}
    throw new Error(msg);
  }
  return r.json();
}

/* --------- i18n --------- */
/*
   Передавайте словарь из Django так:
     {{ i18n_strings|json_script:"rr-i18n" }}
   (в i18n_strings — dict с ключами и переведёнными строками).
*/
const __i18nNode = document.getElementById('rr-i18n');
const I18N = __i18nNode ? JSON.parse(__i18nNode.textContent) : {};
function t(key, fallback) { return I18N[key] || fallback || key; }

/* ---------- Status pill ---------- */
function StatusPill({ status, className }) {
  const labels = {
    draft:     t('status.draft',     'Draft'),
    reserved:  t('status.reserved',  'Reserved'),
    issued:    t('status.issued',    'Issued'),
    returned:  t('status.returned',  'Returned'),
    overdue:   t('status.overdue',   'Overdue'),
    cancelled: t('status.cancelled', 'Cancelled'),
    closed:    t('status.closed',    'Closed'),
  };
  const icons = {
    draft: 'fa-pen-ruler',
    reserved: 'fa-calendar-check',
    issued: 'fa-box-open',
    returned: 'fa-check',
    overdue: 'fa-triangle-exclamation',
    cancelled: 'fa-ban',
    closed: 'fa-circle',
  };
  return (
    <span className={cls('status-pill', status, className)}>
      <i className={`fas ${icons[status] || 'fa-circle'}`} style={{fontSize: 10}}></i>
      {labels[status] || status}
    </span>
  );
}

function Avatar({ user, size }) {
  const s = size || 22;
  const initials = user?.initials ||
                   (user?.name ? user.name.split(' ').slice(0,2).map(x => x[0]).join('').toUpperCase() : '?');
  return (
    <span className="av" style={{ width: s, height: s, fontSize: Math.round(s * 0.42) }}>
      {initials}
    </span>
  );
}

function RoleBadge({ role }) {
  const roleMap = {
    'Mitarbeiter': 'role-staff',
    'Mitglied': 'role-member',
    'Nutzer': 'role-user',
  };
  const cls = roleMap[role] || 'role-user';
  return <span className={`role-badge ${cls}`}>{role}</span>;
}

Object.assign(window, {
  cls, fmtDate, fmtDateShort,
  getCookie, apiPost, apiGet,
  t, StatusPill, Avatar, RoleBadge,
});
