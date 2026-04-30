/* =========================================================
   rental/static/rental/js/detail.jsx
   React islands for rental_detail.html:
     <ActionBar rental urls />
     <RentalTabs rental items rooms issues history urls />
   Depends on: shared.jsx (StatusPill, Avatar, cls, fmtDateShort, apiPost, t)
   ========================================================= */

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
          if (sd.status === 'SIGNED') {
            clearInterval(pollRef.current);
            onSigned();
          } else if (sd.status === 'EXPIRED') {
            clearInterval(pollRef.current);
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
              <button className="btn btn-outline-primary" style={{flex:1,padding:'20px 12px',display:'flex',flexDirection:'column',alignItems:'center',gap:8}} onClick={() => setMode('draw')}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 21h6l11-11a2.2 2.2 0 00-3.1-3.1L6 18v3z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/><path d="M14.5 6.5l3 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                <span style={{fontWeight:600,fontSize:13}}>{t('sig.draw_here', 'Draw here')}</span>
                <span className="muted" style={{fontSize:11}}>{t('sig.draw_desc', 'Draw directly on this device')}</span>
              </button>
              <button className="btn btn-outline-primary" style={{flex:1,padding:'20px 12px',display:'flex',flexDirection:'column',alignItems:'center',gap:8}} onClick={() => { setMode('qr'); doCreateSession(); }} disabled={signBusy}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/><rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/><rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/><path d="M14 14h3v3h-3zM17 17h4M14 20h3M20 14v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                <span style={{fontWeight:600,fontSize:13}}>{t('sig.qr_phone', 'Sign with phone')}</span>
                <span className="muted" style={{fontSize:11}}>{t('sig.qr_desc', 'Scan QR code with your phone')}</span>
              </button>
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

        {mode === 'qr' && (
          <>
            <h5 style={{margin:'0 0 8px',fontSize:16,fontWeight:600}}>{t('sig.qr_title', 'Sign with phone')}</h5>
            <p className="muted" style={{fontSize:13,margin:'0 0 16px'}}>{t('sig.scan_qr', 'Scan the QR code with your phone to sign')}</p>
            {signSessionStatus === 'expired' ? (
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
function ActionBar({ rental, urls }) {
  const status = rental.status;
  const [extendOpen, setExtendOpen] = React.useState(false);
  const [extendTo, setExtendTo] = React.useState(rental.to_iso || '');
  const [extendReason, setExtendReason] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [signModalOpen, setSignModalOpen] = React.useState(false);
  const [signStatus, setSignStatus] = React.useState(rental.has_signature ? 'signed' : 'unsigned');
  const [changeUserOpen, setChangeUserOpen] = React.useState(false);
  const [changePeriodOpen, setChangePeriodOpen] = React.useState(false);
  const dropdownRef = React.useRef(null);

  React.useEffect(() => {
    if (dropdownRef.current && window.bootstrap && window.bootstrap.Dropdown) {
      const dd = window.bootstrap.Dropdown.getOrCreateInstance(dropdownRef.current);
      return () => {
        try {
          dd.dispose();
        } catch (e) {
          console.debug('Dropdown cleanup failed:', e);
        }
      };
    }
  }, []);

  const doExtend = async () => {
    setBusy(true);
    try {
      await apiPost(urls.extend, { to: extendTo, reason: extendReason });
      window.location.reload();
    } catch (e) {
      alert(t('err.extend', 'Could not extend rental: ') + e.message);
      setBusy(false);
    }
  };

  const doMarkIssued = async () => {
    if (!confirm(t('confirm.mark_issued', 'Mark this rental as issued?'))) return;
    setBusy(true);
    try { await apiPost(urls.mark_issued, {}); window.location.reload(); }
    catch (e) { alert(e.message); setBusy(false); }
  };

  const doCancel = async () => {
    if (!confirm(t('confirm.cancel', 'Cancel this rental?'))) return;
    setBusy(true);
    try { await apiPost(urls.cancel, {}); window.location.reload(); }
    catch (e) { alert(e.message); setBusy(false); }
  };

  const doSendReminder = async () => {
    setBusy(true);
    try {
      await apiPost(urls.send_reminder, {});
      alert(t('ok.reminder_sent', 'Reminder sent.'));
    } catch (e) { alert(e.message); }
    setBusy(false);
  };

  const closeSignModal = () => {
    setSignModalOpen(false);
  };

  const scrollTo = (id) => {
    window.dispatchEvent(new CustomEvent('rental-navigate', { detail: id }));
  };

  const doClose = async () => {
    if (!confirm(t('confirm.close', 'Close this rental?'))) return;
    setBusy(true);
    try { await apiPost(urls.close, {}); window.location.reload(); }
    catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <>
      {extendOpen && (
        <div className="inline-extend">
          <i className="fas fa-clock" style={{color:'oklch(0.55 0.14 75)'}}></i>
          <strong style={{color:'oklch(0.38 0.13 75)', fontSize: 12.5}}>
            {t('extend.title', 'Extend return deadline')}
          </strong>
          <span className="muted tiny">{t('extend.from', 'from')}</span>
          <span className="mono" style={{fontSize: 12}}>{fmtDateShort(rental.to_at)}</span>
          <span className="muted tiny">{t('extend.to', 'to')}</span>
          <input type="datetime-local" className="form-control form-control-sm" style={{maxWidth: 200}}
                 value={extendTo} onChange={e => setExtendTo(e.target.value)} />
          <textarea className="form-control form-control-sm ms-2" rows={1}
                    placeholder={t('extend.reason', 'Reason (shown to user)…')}
                    style={{maxWidth: 220}} value={extendReason}
                    onChange={e => setExtendReason(e.target.value)} />
          <div className="ms-auto d-flex" style={{gap: 6}}>
            <button className="btn btn-ghost btn-sm" onClick={() => setExtendOpen(false)} disabled={busy}>
              {t('btn.cancel', 'Cancel')}
            </button>
            <button className="btn btn-primary btn-sm" onClick={doExtend} disabled={busy}>
              <i className="fas fa-check me-1"></i>{t('btn.extend', 'Extend')}
            </button>
          </div>
        </div>
      )}

      <div className="action-bar">
        <div className="primary-cta">
          <StatusPill status={status} />
          <span className="muted tiny">
            {status === 'issued'   && <>{t('due.return_due', 'Return due')}
              <strong style={{color:'var(--ink-2)'}}> {fmtDateShort(rental.to_at)}</strong></>}
            {status === 'overdue'  && <span style={{color:'oklch(0.45 0.14 28)'}}>
              {rental.overdue_days} {t('due.days_overdue', 'days overdue')}</span>}
            {status === 'reserved' && <>{t('due.pickup_at', 'Pickup')}
              <strong> {fmtDateShort(rental.from_at)}</strong></>}
            {status === 'returned' && <>{t('due.closed', 'Closed')}</>}
          </span>
        </div>

        <div className="secondary">
          {status === 'reserved' && (
            <button className="btn btn-primary btn-sm" onClick={doMarkIssued} disabled={busy}>
              <i className="fas fa-box-open me-1"></i>{t('btn.mark_issued', 'Mark issued')}
            </button>
          )}
          {signStatus === 'signed' && (
            <span className="tag tag-ok" style={{display:'inline-flex',alignItems:'center',gap:4}}>
              <i className="fas fa-check-circle" style={{color:'oklch(0.5 0.15 150)'}}></i>{t('sig.signed', 'Signed')}
            </span>
          )}
          {signStatus === 'unsigned' && status === 'reserved' && (
            <button className="btn btn-ghost btn-sm" onClick={() => setSignModalOpen(true)} disabled={busy}>
              <i className="fas fa-signature me-1"></i>{t('btn.request_signature', 'Request signature')}
            </button>
          )}
          {status === 'issued' && (
            <>
              <button className="btn btn-ghost btn-sm" onClick={() => setExtendOpen(o => !o)} disabled={busy}>
                <i className="fas fa-clock me-1"></i>{t('btn.extend', 'Extend')}
              </button>
              <a className="btn btn-primary btn-sm" href={urls.return_page}>
                <i className="fas fa-box-open me-1"></i>{t('btn.start_return', 'Start return')}
              </a>
            </>
          )}
          {status === 'overdue' && (
            <>
              <button className="btn btn-ghost btn-sm" onClick={doSendReminder} disabled={busy}>
                <i className="fas fa-envelope me-1"></i>{t('btn.send_reminder', 'Send reminder')}
              </button>
              <a className="btn btn-primary btn-sm" href={urls.return_page}>
                <i className="fas fa-box-open me-1"></i>{t('btn.start_return', 'Start return')}
              </a>
            </>
          )}
          {status === 'returned' && (
            <button className="btn btn-primary btn-sm" onClick={doClose} disabled={busy}>
              <i className="fas fa-lock me-1"></i>{t('btn.close', 'Close rental')}
            </button>
          )}

          <div className="dropdown">
            <button ref={dropdownRef} className="btn btn-ghost btn-sm" data-bs-toggle="dropdown">
              <i className="fas fa-ellipsis"></i>
            </button>
            <ul className="dropdown-menu dropdown-menu-end shell">
              {(!rental.has_signature && (rental.status === 'draft' || rental.status === 'reserved')) && (
                <li><a className="dropdown-item" href="#items" onClick={e => { e.preventDefault(); scrollTo('items'); }}>
                  <i className="fas fa-pen"></i>{t('menu.edit_items', 'Edit items')}</a></li>
              )}
              {(!rental.has_signature && (rental.status === 'draft' || rental.status === 'reserved')) && (
                <li><a className="dropdown-item" href="#user" onClick={e => { e.preventDefault(); setChangeUserOpen(true); }}>
                  <i className="fas fa-user-pen"></i>{t('menu.change_user', 'Change user')}</a></li>
              )}
              {(!rental.has_signature && (rental.status === 'draft' || rental.status === 'reserved')) && (
                <li><a className="dropdown-item" href="#period" onClick={e => { e.preventDefault(); setChangePeriodOpen(true); }}>
                  <i className="fas fa-calendar-days"></i>{t('menu.edit_period', 'Edit period')}</a></li>
              )}
              <li><hr className="dropdown-divider" /></li>
              <li><button className="dropdown-item" onClick={doSendReminder}>
                <i className="fas fa-envelope"></i>{t('menu.resend_email', 'Resend confirmation')}</button></li>
              <li><a className="dropdown-item" href={urls.export_pdf}>
                <i className="fas fa-file-export"></i>{t('menu.export_pdf', 'Export as PDF')}</a></li>
              <li><hr className="dropdown-divider" /></li>
              <li>
                <button className="dropdown-item" style={{color:'oklch(0.45 0.13 28)'}} onClick={doCancel}>
                  <i className="fas fa-ban"></i>{t('menu.cancel', 'Cancel rental')}
                </button>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {signModalOpen && (
        <SignatureModal
          urls={urls}
          onClose={closeSignModal}
          onSigned={() => { setSignStatus('signed'); setSignModalOpen(false); window.location.reload(); }}
        />
      )}

      {changeUserOpen && (
        <ChangeUserModal
          urls={urls}
          onClose={() => setChangeUserOpen(false)}
          onChanged={() => { setChangeUserOpen(false); window.location.reload(); }}
        />
      )}

      {changePeriodOpen && (
        <ChangePeriodModal
          rental={rental}
          urls={urls}
          onClose={() => setChangePeriodOpen(false)}
          onChanged={() => { setChangePeriodOpen(false); window.location.reload(); }}
        />
      )}
    </>
  );
}

/* ---------- Tabs + contents ---------- */
function RentalTabs({ rental, items, rooms, issues, history, urls }) {
  const [tab, setTab] = React.useState('items');
  const [expanded, setExpanded] = React.useState(null);
  const [reportItem, setReportItem] = React.useState(null);
  const [swapItem, setSwapItem] = React.useState(null);
  const [addItemsOpen, setAddItemsOpen] = React.useState(false);
  const canAddItems = !rental.has_signature && !['returned', 'closed'].includes(rental.status);

  React.useEffect(() => {
    const doNavigate = (target) => {
      if (target === 'items') {
        setTab('items');
        if (!rental.has_signature && (rental.status === 'draft' || rental.status === 'reserved')) {
          setAddItemsOpen(true);
        }
        setTimeout(() => {
          const el = document.getElementById('items');
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
      } else {
        setTimeout(() => {
          const el = document.getElementById(target);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);
      }
    };
    const handleHash = () => { doNavigate(window.location.hash.slice(1)); };
    const handleCustom = (e) => { doNavigate(e.detail); };
    handleHash();
    window.addEventListener('hashchange', handleHash);
    window.addEventListener('rental-navigate', handleCustom);
    return () => {
      window.removeEventListener('hashchange', handleHash);
      window.removeEventListener('rental-navigate', handleCustom);
    };
  }, []);

  return (
    <>
      <div className="soft-tabs">
        <button className={cls(tab === 'items' && 'active')} onClick={() => setTab('items')}>
          {t('tab.equipment', 'Equipment')}<span className="count">{items.length}</span>
        </button>
        <button className={cls(tab === 'rooms' && 'active')} onClick={() => setTab('rooms')}>
          {t('tab.rooms', 'Rooms')}<span className="count">{rooms.length}</span>
        </button>
        <button className={cls(tab === 'issues' && 'active')} onClick={() => setTab('issues')}>
          {t('tab.issues', 'Issues')}<span className="count">{issues.length}</span>
        </button>
        <button className={cls(tab === 'history' && 'active')} onClick={() => setTab('history')}>
          {t('tab.history', 'History')}<span className="count">{history.length}</span>
        </button>
      </div>

          {tab === 'items' && (
        <div className="surface" id="items" style={{padding: 0, overflow: 'hidden'}}>
          {items.map(item => (
            <ItemRow key={item.id} item={item}
                     expanded={expanded === item.id}
                     toggle={() => setExpanded(expanded === item.id ? null : item.id)}
                     urls={urls}
                     status={rental.status}
                     hasSignature={rental.has_signature}
                     onSwapClick={item => setSwapItem(item)}
                     onReportIssue={item => setReportItem(item)}
            />
          ))}
          <div style={{padding:'8px 12px',borderBottom:'1px solid var(--line)',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
            <span className="muted">
              {t('items.total', 'Total:')} {items.length} · {items.reduce((a, i) => a + (i.qty_issued || 0), 0)} {t('items.units_issued', 'units issued')}
            </span>
            {canAddItems && (
            <a className="btn btn-ghost btn-sm ms-auto" href="#items" onClick={e => { e.preventDefault(); setTab('items'); setAddItemsOpen(true); document.getElementById('items')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }}>
              <i className="fas fa-plus me-1"></i>{t('btn.add_item', 'Add item')}
            </a>
            )}
          </div>
        </div>
      )}

      {tab === 'rooms' && (
        <div className="surface" style={{padding: 0, overflow: 'hidden'}}>
          {rooms.length === 0 && (
            <div className="p-4 muted text-center">{t('rooms.none', 'No rooms booked in this rental.')}</div>
          )}
          {rooms.map(room => (
            <div key={room.id} style={{padding: '14px 16px', borderBottom: '1px solid var(--line)',
                                          display:'grid', gridTemplateColumns: '40px 1fr auto', gap: 12, alignItems:'center'}}>
              <span className="av" style={{width: 40, height: 40, fontSize: 14}}>
                <i className="fas fa-door-open"></i>
              </span>
              <div>
                <div style={{fontWeight: 600, fontSize: 14}}>{room.name}</div>
                <div className="muted tiny">{room.period} · {room.seat}</div>
              </div>
              <span className="tag tag-hold">{t('room.booked', 'Booked')}</span>
            </div>
          ))}
        </div>
      )}

      {tab === 'issues' && (
        <IssuesPanel issues={issues} urls={urls} onReportIssue={setReportItem} />
      )}

      {reportItem !== null && <ReportIssueModal item={reportItem} onClose={() => setReportItem(null)} urls={urls} />}
      {swapItem !== null && <SwapUnitModal item={swapItem} onClose={() => setSwapItem(null)} urls={urls} rental={rental} />}
      {addItemsOpen && canAddItems && <AddItemsModal rental={rental} urls={urls} existingItems={items} onClose={() => setAddItemsOpen(false)} />}

      {tab === 'history' && (
        <div className="surface" style={{padding: '4px 0'}}>
          {history.map((e, i) => (
            <div key={i} style={{display:'grid', gridTemplateColumns:'140px 28px 1fr', gap: 10, alignItems:'start',
                                    padding: '12px 16px', borderBottom: i < history.length - 1 ? '1px solid var(--line)' : 'none',
                                    fontSize: 13}}>
              <div className="muted tiny mono">{fmtDateShort(e.at)}</div>
              <div style={{width: 20, height: 20, borderRadius: 999, background: 'var(--bg-sub)',
                             border: '1px solid var(--line)', display:'flex', alignItems:'center', justifyContent:'center',
                             fontSize: 10, color:'var(--ink-3)'}}>
                <i className="fas fa-circle" style={{fontSize: 6}}></i>
              </div>
              <div>
                <strong style={{fontSize: 13}}>{e.who}</strong>
                <span className="muted"> — {e.what}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

/* ---------- Add Items Modal ---------- */
function AddItemsModal({ rental, urls, existingItems, onClose }) {
  const [searchQuery, setSearchQuery] = React.useState('');
  const [results, setResults] = React.useState([]);
  const [selected, setSelected] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const existingNums = React.useMemo(() => new Set((existingItems || []).map(item => item.num)), [existingItems]);

  React.useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => {
      const params = new URLSearchParams();
      if (rental && rental.pk) params.set('rental_id', rental.pk);
      if (rental && rental.from_at) params.set('from', rental.from_at);
      if (rental && rental.to_at) params.set('to', rental.to_at);
      if (searchQuery.trim()) params.set('q', searchQuery.trim());
      apiGet(`${urls.inventory_search}?${params}`)
        .then(data => setResults(data.items || []))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, searchQuery ? 250 : 0);
    return () => clearTimeout(timer);
  }, [searchQuery, rental]);

  const availableResults = React.useMemo(() => {
    return results.filter(item => !existingNums.has(item.num));
  }, [results, existingNums]);

  const isSelected = id => selected.some(item => item.id === id);
  const toggleItem = item => {
    if (item.conflict || item.qty?.avail <= 0) return;
    setSelected(items => isSelected(item.id)
      ? items.filter(existing => existing.id !== item.id)
      : [...items, { id: item.id, name: item.name, num: item.num, qty: 1 }]
    );
  };

  const doAdd = async () => {
    if (!selected.length) return;
    setBusy(true);
    try {
      await apiPost(urls.add_items, { items: selected });
      window.location.reload();
    } catch (e) {
      alert(t('err.add_items', 'Could not add items: ') + e.message);
      setBusy(false);
    }
  };

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.3)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:9999}} onClick={onClose}>
      <div style={{background:'#fff',borderRadius:12,padding:20,width:720,maxWidth:'94vw',maxHeight:'84vh',display:'flex',flexDirection:'column'}} onClick={e => e.stopPropagation()}>
        <h6 style={{margin:'0 0 12px',fontSize:13,textTransform:'uppercase',letterSpacing:'.04em',color:'var(--ink-3)',fontWeight:600}}>
          {t('add_items.title', 'Add items to rental')}
        </h6>
        <div className="search" style={{maxWidth:'100%',marginBottom:10}}>
          <i className="fas fa-search"></i>
          <input type="text" className="form-control form-control-sm" placeholder={t('add_items.search', 'Search inventory…')}
                 value={searchQuery} onChange={e => setSearchQuery(e.target.value)} autoFocus />
        </div>
        <div style={{flex:1,overflowY:'auto',minHeight:240,maxHeight:430,border:'1px solid var(--line)',borderRadius:8}}>
          {loading && <div className="p-3 muted text-center">{t('loading', 'Loading…')}</div>}
          {!loading && availableResults.length === 0 && <div className="p-3 muted text-center">{t('add_items.none', 'No available items found')}</div>}
          {!loading && availableResults.slice(0, 100).map(item => {
            const unavailable = item.conflict || item.qty?.avail <= 0;
            const selectedItem = isSelected(item.id);
            return (
              <div key={item.id} className={cls('item-row-selectable', selectedItem && 'selected', unavailable && 'unavailable')}
                   style={{padding:'9px 12px',borderBottom:'1px solid var(--line)',cursor: unavailable ? 'not-allowed' : 'pointer',display:'grid',gridTemplateColumns:'32px 86px 1fr 120px 90px',gap:10,alignItems:'center',fontSize:13,opacity: unavailable ? 0.62 : 1}}
                   onClick={() => toggleItem(item)}>
                <input type="checkbox" className="form-check-input" checked={selectedItem} readOnly disabled={unavailable} />
                <span className="mono muted" style={{fontSize:11}}>{item.num || '—'}</span>
                <div style={{minWidth:0}}>
                  <div style={{fontWeight:500,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{item.name || '—'}</div>
                  <div className="muted tiny">{item.cat || '—'}</div>
                </div>
                <span className="muted tiny">{item.loc || '—'}</span>
                <span className={cls('tag', unavailable ? 'tag-hold' : 'tag-ok')}>
                  {unavailable ? (item.status_label || t('tag.booked', 'Booked')) : `${item.qty.avail}/${item.qty.total}`}
                </span>
              </div>
            );
          })}
        </div>
        <div style={{display:'flex',gap:8,alignItems:'center',justifyContent:'flex-end',marginTop:12}}>
          <span className="muted tiny me-auto">{selected.length} {t('add_items.selected', 'selected')}</span>
          <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>{t('btn.cancel', 'Cancel')}</button>
          <button className="btn btn-primary btn-sm" onClick={doAdd} disabled={busy || !selected.length}>
            <i className="fas fa-plus me-1"></i>{t('add_items.confirm', 'Add selected items')}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Report Issue Modal ---------- */
function ReportIssueModal({ item, onClose, urls }) {
  const [severity, setSeverity] = React.useState('minor');
  const [description, setDescription] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  const submit = async () => {
    if (!description.trim()) return;
    setBusy(true);
    try {
      await apiPost(urls.report_issue, {
        item_id: item ? item.id : undefined,
        severity,
        description,
      });
      window.location.reload();
    } catch (e) {
      alert(e.message);
      setBusy(false);
    }
  };

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.3)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:9999}} onClick={onClose}>
      <div style={{background:'#fff',borderRadius:12,padding:20,width:400,maxWidth:'90vw'}} onClick={e => e.stopPropagation()}>
        <h6 style={{margin:'0 0 12px',fontSize:13,textTransform:'uppercase',letterSpacing:'.04em',color:'var(--ink-3)',fontWeight:600}}>
          {item ? t('report.title_item', 'Report issue') + ': ' + item.name : t('report.title', 'Log issue')}
        </h6>
        <div style={{marginBottom:10}}>
          <label style={{fontSize:12,display:'block',marginBottom:4,color:'var(--ink-3)'}}>{t('report.severity', 'Severity')}</label>
          <select className="form-select form-select-sm" value={severity} onChange={e => setSeverity(e.target.value)}>
            <option value="minor">{t('sev.minor', 'Minor')}</option>
            <option value="major">{t('sev.major', 'Major')}</option>
            <option value="critical">{t('sev.critical', 'Critical')}</option>
          </select>
        </div>
        <div style={{marginBottom:12}}>
          <label style={{fontSize:12,display:'block',marginBottom:4,color:'var(--ink-3)'}}>{t('report.description', 'Description')}</label>
          <textarea className="form-control form-control-sm" rows={3} value={description}
                    onChange={e => setDescription(e.target.value)}
                    placeholder={t('report.placeholder', 'Describe the issue…')} />
        </div>
        <div style={{display:'flex',gap:8,justifyContent:'flex-end'}}>
          <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>{t('btn.cancel', 'Cancel')}</button>
          <button className="btn btn-primary btn-sm" onClick={submit} disabled={busy || !description.trim()}>
            <i className="fas fa-check me-1"></i>{t('btn.submit', 'Submit')}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Item row with expand ---------- */
function ItemRow({ item, expanded, toggle, urls, onReportIssue, onSwapClick, status, hasSignature }) {
  const fullyReturned = (item.qty_returned || 0) >= (item.qty_issued || 0);
  const canSwap = status && ['draft', 'reserved'].includes(status);
  return (
    <>
      <div className={cls('item-detail-row', expanded && 'expanded')} onClick={toggle} style={{cursor:'pointer'}}>
        <i className={`fas fa-chevron-${expanded ? 'down' : 'right'} muted`} style={{fontSize: 11}}></i>
        <div>
          <div className="name">{item.name}</div>
          <div className="sub"><span className="mono">{item.num}</span> · {item.cat}</div>
        </div>
        <div className="qty-grid">
          <div><div className="v">{item.qty_requested || 0}</div><div className="l">{t('qty.req', 'req')}</div></div>
          <div><div className="v">{item.qty_issued   || 0}</div><div className="l">{t('qty.issued', 'issued')}</div></div>
          <div><div className="v">{item.qty_returned || 0}</div><div className="l">{t('qty.back', 'back')}</div></div>
        </div>
        <div>
          {fullyReturned
            ? <span className="tag tag-ok">{t('tag.returned', 'Returned')}</span>
            : <span className="tag tag-warn">{t('tag.out', 'Out')}</span>}
        </div>
        <div className="muted tiny">{fmtDateShort(item.issued_at)}</div>
      </div>
      {expanded && (
        <div className="expand-panel">
          <div className="kv">
            <span className="k">{t('item.location', 'Location')}</span><span>{item.loc}</span>
            <span className="k">{t('item.owner', 'Owner dept.')}</span><span>{item.owner}</span>
            <span className="k">{t('item.issued_at', 'Issued at')}</span><span>{fmtDateShort(item.issued_at)}</span>
            <span className="k">{t('item.notes', 'Asset notes')}</span><span>{item.notes || <span className="muted">—</span>}</span>
          </div>
          <div className="mt-2 d-flex" style={{gap: 6}}>
            {canSwap && !hasSignature && (
              <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); onSwapClick(item); }}>
                <i className="fas fa-arrow-right-arrow-left me-1"></i>{t('btn.swap', 'Swap unit')}
              </button>
            )}
            {(status === 'draft' || status === 'reserved') && !hasSignature && (
              <button className="btn btn-ghost btn-sm" onClick={async (e) => {
                e.stopPropagation();
                if (!confirm(t('confirm.remove', 'Remove this item from the rental?'))) return;
                try {
                  await apiPost(urls.remove_item, { item_id: item.id });
                  window.location.reload();
                } catch (e) { alert(e.message); }
              }}>
                <i className="fas fa-circle-minus me-1"></i>{t('btn.remove', 'Remove from rental')}
              </button>
            )}
            <button className="btn btn-ghost btn-sm" onClick={() => onReportIssue(item)}>
              <i className="fas fa-triangle-exclamation me-1"></i>{t('btn.report_issue', 'Report issue')}
            </button>
          </div>
        </div>
      )}
    </>
  );
}

/* ---------- Issues tab ---------- */
function IssuesPanel({ issues, onReportIssue }) {
  return (
    <>
      <div style={{display:'flex', alignItems:'center', marginBottom: 10, gap: 10}}>
        <div className="muted tiny">
          {t('issues.note', "Issues are logged during return — they don't affect item availability until closed.")}
        </div>
        <button className="btn btn-ghost btn-sm ms-auto" onClick={() => onReportIssue(null)}>
          <i className="fas fa-plus me-1"></i>{t('btn.log_issue', 'Log issue')}
        </button>
      </div>
      <div className="surface" style={{padding: 0, overflow: 'hidden'}}>
        {issues.length === 0 && (
          <div className="p-4 muted text-center">{t('issues.none', 'No issues logged.')}</div>
        )}
        {issues.map(iss => (
          <div key={iss.id} className={cls('issue-row',
                                           iss.severity === 'major' && 'severity-major',
                                           iss.severity === 'critical' && 'severity-critical')}>
            <span className="sev-dot"></span>
            <div>
              <div className="issue-name">{iss.item}</div>
              <div className="issue-sub">
                <span className="mono">{iss.num}</span> · {iss.desc}
              </div>
            </div>
            <div className="muted tiny">
              {iss.severity === 'minor' && <span className="tag tag-warn">{t('sev.minor', 'Minor')}</span>}
              {iss.severity === 'major' && <span className="tag tag-bad"
                style={{background:'oklch(0.97 0.05 45)', color:'oklch(0.40 0.14 45)', borderColor:'oklch(0.85 0.1 45)'}}>
                {t('sev.major', 'Major')}
              </span>}
              {iss.severity === 'critical' && <span className="tag tag-bad">{t('sev.critical', 'Critical')}</span>}
            </div>
            <div className="muted tiny">
              <div>{iss.by}</div>
              <div>{fmtDateShort(iss.at)}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

/* ---------- Swap Unit Modal ---------- */
function SwapUnitModal({ item, onClose, urls, rental, onSwapped }) {
  const [searchQuery, setSearchQuery] = React.useState('');
  const [results, setResults] = React.useState([]);
  const [selected, setSelected] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    loadInventory();
  }, []);

  const loadInventory = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (rental && rental.pk) params.set('rental_id', rental.pk);
      if (rental && rental.from_at) params.set('from', rental.from_at);
      if (rental && rental.to_at) params.set('to', rental.to_at);
      const qs = params.toString();
      const url = urls.inventory_search + (qs ? '?' + qs : '');
      const data = await apiGet(url);
      setResults(data.items || data.results || []);
    } catch (e) {
      console.error('Failed to load inventory:', e);
    }
    setLoading(false);
  };

  const filtered = React.useMemo(() => {
    if (!searchQuery.trim()) return results;
    const q = searchQuery.toLowerCase();
    return results.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      (r.num || '').toLowerCase().includes(q) ||
      (r.cat || '').toLowerCase().includes(q)
    );
  }, [searchQuery, results]);

  const doSwap = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await apiPost(urls.swap_item, {
        current_item_id: item.id,
        new_inventory_item_id: selected.id,
      });
      if (onSwapped) onSwapped();
      window.location.reload();
    } catch (e) {
      alert(t('err.swap', 'Could not swap item: ') + e.message);
      setBusy(false);
    }
  };

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.3)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:9999}} onClick={onClose}>
      <div style={{background:'#fff',borderRadius:12,padding:20,width:520,maxWidth:'90vw',maxHeight:'80vh',display:'flex',flexDirection:'column'}} onClick={e => e.stopPropagation()}>
        <h6 style={{margin:'0 0 12px',fontSize:13,textTransform:'uppercase',letterSpacing:'.04em',color:'var(--ink-3)',fontWeight:600}}>
          {t('swap.title', 'Swap')}: {item.name}
        </h6>
        <div style={{marginBottom:10}}>
          <input type="text" className="form-control form-control-sm" placeholder={t('swap.search', 'Search inventory…')}
                 value={searchQuery} onChange={e => setSearchQuery(e.target.value)} autoFocus />
        </div>
        <div style={{flex:1,overflowY:'auto',minHeight:200,maxHeight:350,border:'1px solid var(--line)',borderRadius:8}}>
          {loading && <div className="p-3 muted text-center">{t('loading', 'Loading…')}</div>}
          {!loading && filtered.length === 0 && <div className="p-3 muted text-center">{t('swap.no_results', 'No items found')}</div>}
          {filtered.slice(0, 100).map(inv => (
            <div key={inv.id} className={cls('item-row-selectable', selected && selected.id === inv.id && 'selected')}
                 style={{padding:'8px 12px',borderBottom:'1px solid var(--line)',cursor: inv.conflict ? 'not-allowed' : 'pointer',
                         display:'flex',gap:10,alignItems:'center',fontSize:13,
                         background: selected && selected.id === inv.id ? 'var(--bg-accent)' : 'transparent',
                         opacity: inv.conflict ? 0.5 : 1}}
                 onClick={() => !inv.conflict && setSelected(inv)}>
              <span className="mono muted" style={{fontSize:11,minWidth:50}}>{inv.num || '—'}</span>
              <span style={{flex:1}}>{inv.name || '—'}</span>
              <span className="muted tiny">{inv.cat || '—'}</span>
              {inv.qty && <span className={cls('tag', inv.conflict ? 'tag-warn' : 'tag-ok')}
                                style={{fontSize:11,padding:'2px 6px'}}>
                {inv.conflict ? t('swap.unavailable', 'Unavailable') : `${inv.qty.avail}/${inv.qty.total}`}
              </span>}
            </div>
          ))}
        </div>
        <div style={{display:'flex',gap:8,justifyContent:'flex-end',marginTop:12}}>
          <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>{t('btn.cancel', 'Cancel')}</button>
          <button className="btn btn-primary btn-sm" onClick={doSwap} disabled={busy || !selected}>
            <i className="fas fa-check me-1"></i>{t('btn.swap_confirm', 'Confirm swap')}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Change User Modal ---------- */
function ChangeUserModal({ urls, onClose, onChanged }) {
  const [q, setQ] = React.useState('');
  const [users, setUsers] = React.useState([]);
  const [selected, setSelected] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!q || q.length < 2) { setUsers([]); return; }
    setLoading(true);
    const timer = setTimeout(() => {
      apiGet(urls.users_search + '?q=' + encodeURIComponent(q))
        .then(data => setUsers(data.users || []))
        .catch(() => setUsers([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [q]);

  const doChange = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await apiPost(urls.change_user, { user_id: selected.id });
      if (onChanged) onChanged();
      window.location.reload();
    } catch (e) {
      alert(t('err.change_user', 'Could not change user: ') + e.message);
      setBusy(false);
    }
  };

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.3)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:9999}} onClick={onClose}>
      <div style={{background:'#fff',borderRadius:12,padding:20,width:560,maxWidth:'90vw',maxHeight:'80vh',display:'flex',flexDirection:'column'}} onClick={e => e.stopPropagation()}>
        <h6 style={{margin:'0 0 12px',fontSize:13,textTransform:'uppercase',letterSpacing:'.04em',color:'var(--ink-3)',fontWeight:600}}>
          {t('change_user.title', 'Change user')}
        </h6>
        <div style={{marginBottom:10}}>
          <div className="search" style={{maxWidth:'100%'}}>
            <i className="fas fa-search"></i>
            <input type="text" className="form-control form-control-sm"
                   placeholder={t('change_user.search', 'Search by name, email…')}
                   value={q} onChange={e => setQ(e.target.value)} autoFocus />
          </div>
        </div>
        <div style={{flex:1,overflowY:'auto',minHeight:200,maxHeight:350,border:'1px solid var(--line)',borderRadius:8}}>
          {loading && <div className="p-3 muted text-center">{t('loading', 'Searching…')}</div>}
          {!loading && users.length === 0 && q.length >= 2 && <div className="p-3 muted text-center">{t('change_user.no_results', 'No users found')}</div>}
          {!loading && q.length < 2 && <div className="p-3 muted text-center">{t('change_user.type_hint', 'Type at least 2 characters to search')}</div>}
          {users.map(u => (
            <div key={u.id} className={cls('item-row-selectable', selected && selected.id === u.id && 'selected')}
                 style={{padding:'8px 12px',borderBottom:'1px solid var(--line)',cursor:'pointer',display:'flex',gap:10,alignItems:'center',fontSize:13,
                         background: selected && selected.id === u.id ? 'var(--brand-bg)' : undefined}}
                 onClick={() => setSelected(u)}>
              <Avatar user={u} size={32} />
              <div style={{minWidth:0}}>
                <div style={{fontWeight:500}}>{u.name}</div>
                <div className="muted tiny">{u.org} · <RoleBadge role={u.role} /> · {u.past || 0} {t('user.past_rentals','past rentals')}</div>
              </div>
              {selected && selected.id === u.id && <i className="fas fa-check" style={{color:'var(--brand)',marginLeft:'auto'}}></i>}
            </div>
          ))}
        </div>
        <div style={{display:'flex',gap:8,justifyContent:'flex-end',marginTop:12}}>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>{t('btn.cancel', 'Cancel')}</button>
          <button className="btn btn-primary btn-sm" onClick={doChange} disabled={busy || !selected}>
            <i className="fas fa-user-pen me-1"></i>{t('btn.change_user', 'Change user')}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Change Period Modal ---------- */
function ChangePeriodModal({ rental, urls, onClose, onChanged }) {
  const fromIso = rental.from_at ? rental.from_at.slice(0, 16) : '';
  const toIso = rental.to_at ? rental.to_at.slice(0, 16) : '';
  const [newFrom, setNewFrom] = React.useState(fromIso);
  const [newTo, setNewTo] = React.useState(toIso);
  const [busy, setBusy] = React.useState(false);

  const doChange = async () => {
    if (!newFrom || !newTo) { alert(t('change_period.required', 'Both dates are required.')); return; }
    setBusy(true);
    try {
      await apiPost(urls.change_period, { from: newFrom, to: newTo });
      if (onChanged) onChanged();
      window.location.reload();
    } catch (e) {
      alert(t('err.change_period', 'Could not change period: ') + e.message);
      setBusy(false);
    }
  };

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.3)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:9999}} onClick={onClose}>
      <div style={{background:'#fff',borderRadius:12,padding:20,width:440,maxWidth:'90vw'}} onClick={e => e.stopPropagation()}>
        <h6 style={{margin:'0 0 16px',fontSize:13,textTransform:'uppercase',letterSpacing:'.04em',color:'var(--ink-3)',fontWeight:600}}>
          {t('change_period.title', 'Edit rental period')}
        </h6>
        <div style={{marginBottom:12}}>
          <label style={{fontSize:12,fontWeight:500,display:'block',marginBottom:4}}>{t('change_period.from', 'Pickup date')}</label>
          <input type="datetime-local" className="form-control form-control-sm" value={newFrom} onChange={e => setNewFrom(e.target.value)} />
        </div>
        <div style={{marginBottom:16}}>
          <label style={{fontSize:12,fontWeight:500,display:'block',marginBottom:4}}>{t('change_period.to', 'Return date')}</label>
          <input type="datetime-local" className="form-control form-control-sm" value={newTo} onChange={e => setNewTo(e.target.value)} />
        </div>
        <div style={{display:'flex',gap:8,justifyContent:'flex-end'}}>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>{t('btn.cancel', 'Cancel')}</button>
          <button className="btn btn-primary btn-sm" onClick={doChange} disabled={busy}>
            <i className="fas fa-calendar-days me-1"></i>{t('btn.save_period', 'Save period')}
          </button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ActionBar, RentalTabs });
