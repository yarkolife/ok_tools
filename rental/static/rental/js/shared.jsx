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

/* --------- frontend flags --------- */
const __flagsNode = document.getElementById('rr-flags');
const FLAGS = __flagsNode ? JSON.parse(__flagsNode.textContent) : {};

/* Short tone after a barcode scan. Silent unless the counter switched the
   sound on in the rental configuration: several people share one desk. */
function beep(freq, dur) {
  if (!FLAGS.scan_sound) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = freq;
    osc.type = 'square';
    gain.gain.value = 0.1;
    osc.start();
    osc.stop(ctx.currentTime + dur / 1000);
  } catch (e) {}
}

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

function RoleBadge({ role, roleKey }) {
  // `roleKey` comes from the serializer and is language independent; the name
  // map stays as a fallback for callers that only pass the translated label.
  const keyMap = {
    employee: 'role-staff',
    member: 'role-member',
    rental_only: 'role-rental-only',
    user: 'role-user',
  };
  const nameMap = {
    'Mitarbeiter': 'role-staff',
    'Mitglied': 'role-member',
    'Nutzer': 'role-user',
  };
  const cls = keyMap[roleKey] || nameMap[role] || 'role-user';
  return <span className={`role-badge ${cls}`}>{role}</span>;
}

/* ---------- Signature Modal (Draw + QR) ---------- */
function SignatureModal({ urls, onClose, onSigned }) {
  const [mode, setMode] = React.useState(null);
  const [signQrUrl, setSignQrUrl] = React.useState(null);
  const [signSessionStatus, setSignSessionStatus] = React.useState(null);
  const [signBusy, setSignBusy] = React.useState(false);
  const [drawBusy, setDrawBusy] = React.useState(false);
  const [drawError, setDrawError] = React.useState(null);
  const padRef = React.useRef(null);
  const canvasRef = React.useRef(null);
  const pollRef = React.useRef(null);

  const initPad = React.useCallback(() => {
    if (canvasRef.current && window.SignaturePad) {
      const ratio = Math.max(window.devicePixelRatio || 1, 1);
      const c = canvasRef.current;
      c.width = c.offsetWidth * ratio;
      c.height = c.offsetHeight * ratio;
      c.getContext('2d').scale(ratio, ratio);
      if (padRef.current) padRef.current.clear();
      padRef.current = new window.SignaturePad(c, {
        minWidth: 1, maxWidth: 2.8, penColor: '#111111',
      });
    }
  }, []);

  React.useEffect(() => {
    if (mode === 'draw') {
      const timer = setTimeout(initPad, 50);
      return () => clearTimeout(timer);
    }
  }, [mode, initPad]);

  const doCreateSession = async () => {
    setSignBusy(true);
    try {
      const data = await apiPost(urls.create_sign_session, {});
      setSignQrUrl(`/rental/sign-session/${data.token}/qr/`);
      setSignSessionStatus('pending');
      pollRef.current = setInterval(async () => {
        try {
          const sd = await apiGet(`/rental/sign-session/${data.token}/status/?consume=1`);
          const normalizedStatus = String(sd.status || '').toLowerCase();
          if (normalizedStatus === 'signed') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setSignSessionStatus('signed');
            setTimeout(onSigned, 1800);
          } else if (normalizedStatus === 'expired') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setSignSessionStatus('expired');
          }
        } catch (e) {
          console.debug('Signature session polling failed:', e);
        }
      }, 3000);
    } catch (e) {
      alert(t('err.sign_session', 'Could not create signing session: ') + e.message);
    }
    setSignBusy(false);
  };

  const doDrawSave = async () => {
    if (!padRef.current || padRef.current.isEmpty()) {
      alert(t('sig.draw_empty', 'Please draw a signature first.'));
      return;
    }
    setDrawBusy(true);
    setDrawError(null);
    try {
      const svgData = padRef.current.toSVG();
      const pointsData = padRef.current.toData();
      const metadata = {
        captured_at: new Date().toISOString(),
        user_agent: navigator.userAgent,
        max_touch_points: navigator.maxTouchPoints || 0,
      };
      await apiPost(urls.save_signature, {
        signature_svg: svgData,
        signature_points: JSON.stringify(pointsData),
        signature_metadata: JSON.stringify(metadata),
        signature_method: 'mouse',
      });
      onSigned();
    } catch (e) {
      setDrawError(e.message || t('err.save_sig', 'Failed to save signature.'));
    }
    setDrawBusy(false);
  };

  const closeAll = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    onClose();
  };

  const modalBg = {position:'fixed',inset:0,background:'rgba(0,0,0,0.3)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:9999};
  const card = {background:'#fff',borderRadius:12,padding:24,width:620,maxWidth:'95vw',maxHeight:'90vh',overflowY:'auto'};

  return (
    <div style={modalBg} onClick={closeAll}>
      <div style={card} onClick={e => e.stopPropagation()}>

        {!mode && (
          <>
            <h5 style={{margin:'0 0 8px',fontSize:16,fontWeight:600}}>{t('sig.title', 'Digital Signature')}</h5>
            <p className="muted" style={{fontSize:13,margin:'0 0 20px'}}>{t('sig.choose', 'Choose a signing method. Drawing directly is recommended for tablets.')}</p>
            <div style={{display:'flex',gap:12}}>
              <button className="btn btn-outline-primary sig-choice" onClick={() => setMode('draw')}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 21h6l11-11a2.2 2.2 0 00-3.1-3.1L6 18v3z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/><path d="M14.5 6.5l3 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                <span style={{fontWeight:600,fontSize:13}}>{t('sig.draw_here', 'Draw here')}</span>
                <span className="sig-choice-desc">{t('sig.draw_desc', 'Draw directly on this device')}</span>
              </button>
              <button className="btn btn-outline-primary sig-choice" onClick={() => { setMode('qr'); doCreateSession(); }} disabled={signBusy}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/><rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/><rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/><path d="M14 14h3v3h-3zM17 17h4M14 20h3M20 14v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                <span style={{fontWeight:600,fontSize:13}}>{t('sig.qr_phone', 'Sign with phone')}</span>
                <span className="sig-choice-desc">{t('sig.qr_desc', 'Scan QR code with your phone')}</span>
              </button>
              {(urls.print_slips || []).length > 0 && (
                <button className="btn btn-outline-primary sig-choice" onClick={() => setMode('paper')}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M7 8V3h10v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/><rect x="4" y="8" width="16" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/><path d="M7 15h10v6H7z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/></svg>
                  <span style={{fontWeight:600,fontSize:13}}>{t('sig.print', 'Sign on paper')}</span>
                  <span className="sig-choice-desc">{t('sig.print_desc', 'Print the issue slip and sign it by hand')}</span>
                </button>
              )}
            </div>
            <div style={{marginTop:16,textAlign:'right'}}>
              <button className="btn btn-ghost btn-sm" onClick={closeAll}>{t('btn.cancel', 'Cancel')}</button>
            </div>
          </>
        )}

        {mode === 'draw' && (
          <>
            <h5 style={{margin:'0 0 8px',fontSize:16,fontWeight:600}}>{t('sig.draw_title', 'Draw your signature')}</h5>
            <p className="muted" style={{fontSize:13,margin:'0 0 12px'}}>{t('sig.draw_hint', 'Sign below using your finger or stylus.')}</p>
            <div style={{background:'#f8f9fa',borderRadius:8,padding:4,position:'relative'}}>
              <canvas ref={canvasRef} style={{width:'100%',height:180,cursor:'crosshair',touchAction:'none',userSelect:'none'}}></canvas>
              <div style={{position:'absolute',top:8,left:12,right:12,bottom:12,border:'1px dashed #bbb',pointerEvents:'none',borderRadius:4}}></div>
            </div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginTop:12}}>
              <button className="btn btn-outline-secondary btn-sm" onClick={() => { if (padRef.current) { padRef.current.clear(); } }}>{t('sig.clear', 'Clear')}</button>
              <div style={{display:'flex',gap:8}}>
                <button className="btn btn-ghost btn-sm" onClick={() => setMode(null)}>{t('btn.cancel', 'Cancel')}</button>
                <button className="btn btn-primary btn-sm" onClick={doDrawSave} disabled={drawBusy}>
                  <i className="fas fa-check me-1"></i>{drawBusy ? t('sig.saving', 'Saving…') : t('sig.submit', 'Submit signature')}
                </button>
              </div>
            </div>
            {drawError && <div className="alert alert-danger mt-2" style={{fontSize:13}}>{drawError}</div>}
          </>
        )}

        {mode === 'paper' && (
          <>
            <h5 style={{margin:'0 0 8px',fontSize:16,fontWeight:600}}>{t('sig.print', 'Sign on paper')}</h5>
            <p className="muted" style={{fontSize:13,margin:'0 0 16px'}}>
              {(urls.print_slips || []).length > 1
                ? t('sig.print_multi', 'Items of different owners are printed on different forms. Print each slip the rental needs.')
                : t('sig.print_desc', 'Print the issue slip and sign it by hand')}
            </p>
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              {(urls.print_slips || []).map(slip => (
                <a key={slip.url} className="btn btn-outline-primary"
                   style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,textDecoration:'none'}}
                   href={slip.url} target="_blank" rel="noopener">
                  <span style={{fontWeight:600,fontSize:13}}>{slip.org_name}</span>
                  <span style={{fontSize:11,opacity:.85}}><i className="fas fa-print me-1"></i>{t('btn.print', 'Print')}</span>
                </a>
              ))}
            </div>
            <div style={{marginTop:16,display:'flex',justifyContent:'space-between'}}>
              <button className="btn btn-ghost btn-sm" onClick={() => setMode(null)}>{t('btn.back', 'Back')}</button>
              <button className="btn btn-primary btn-sm" onClick={closeAll}>{t('btn.done', 'Done')}</button>
            </div>
          </>
        )}

        {mode === 'qr' && (
          <>
            <h5 style={{margin:'0 0 8px',fontSize:16,fontWeight:600}}>{t('sig.qr_title', 'Sign with phone')}</h5>
            <p className="muted" style={{fontSize:13,margin:'0 0 16px'}}>{t('sig.scan_qr', 'Scan the QR code with your phone to sign')}</p>
            {signSessionStatus === 'signed' ? (
              <div style={{textAlign:'center',padding:24,background:'#f0fdf4',border:'1px solid #bbf7d0',borderRadius:8}}>
                <i className="fas fa-circle-check" style={{fontSize:34,color:'#15803d',marginBottom:10}}></i>
                <p style={{fontWeight:700,margin:'0 0 4px',color:'#166534'}}>{t('sig.received_title', 'Signature received')}</p>
                <p className="muted tiny" style={{margin:0}}>{t('sig.received_desc', 'The phone signature was transferred to this rental. The page will update automatically.')}</p>
              </div>
            ) : signSessionStatus === 'expired' ? (
              <div style={{textAlign:'center',padding:24}}>
                <i className="fas fa-clock" style={{fontSize:32,color:'var(--ink-4)',marginBottom:8}}></i>
                <p>{t('sig.expired', 'Signing session expired. Please try again.')}</p>
                <button className="btn btn-ghost btn-sm" onClick={() => { setSignSessionStatus(null); doCreateSession(); }}>{t('sig.retry', 'Retry')}</button>
              </div>
            ) : (
              <div style={{background:'#f8f9fa',borderRadius:8,padding:16,textAlign:'center'}}>
                {signQrUrl ? (
                  <img src={signQrUrl} alt="QR Code" style={{width:200,height:200,margin:'0 auto'}} onError={e => { e.target.style.display='none'; }} />
                ) : (
                  <div className="muted p-4"><i className="fas fa-spinner fa-spin" style={{fontSize:24}}></i></div>
                )}
                <p className="muted tiny" style={{marginTop:12}}>{t('sig.auto_check', 'Status will update automatically')}</p>
                {signSessionStatus === 'pending' && <p className="muted tiny" style={{color:'oklch(0.55 0.15 250)'}}><i className="fas fa-hourglass-half me-1"></i>{t('sig.waiting', 'Waiting for signature…')}</p>}
              </div>
            )}
            <div style={{marginTop:16,textAlign:'right'}}>
              <button className="btn btn-ghost btn-sm" onClick={closeAll}>{t('btn.close', 'Close')}</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

Object.assign(window, {
  cls, fmtDate, fmtDateShort,
  getCookie, apiPost, apiGet,
  t, FLAGS, beep, StatusPill, Avatar, RoleBadge, SignatureModal,
});
