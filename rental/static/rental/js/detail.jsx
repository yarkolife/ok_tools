/* =========================================================
   rental/static/rental/js/detail.jsx
   React islands for rental_detail.html:
     <ActionBar rental urls />
     <RentalTabs rental items rooms issues history urls />
   Depends on: shared.jsx (StatusPill, Avatar, cls, fmtDateShort, apiPost, t)
   ========================================================= */

/* ---------- Action bar — CTA driven by status + extend + overflow ---------- */
function ActionBar({ rental, urls }) {
  const [status, setStatus] = React.useState(rental.status);
  const [extendOpen, setExtendOpen] = React.useState(false);
  const [extendTo, setExtendTo] = React.useState(rental.to_iso || '');
  const [extendReason, setExtendReason] = React.useState('');
  const [busy, setBusy] = React.useState(false);

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
            <form method="POST" action={urls.close} style={{display:'inline'}}>
              <input type="hidden" name="csrfmiddlewaretoken" value={getCookie('csrftoken')} />
              <button className="btn btn-primary btn-sm" type="submit">
                <i className="fas fa-lock me-1"></i>{t('btn.close', 'Close rental')}
              </button>
            </form>
          )}

          <div className="dropdown">
            <button className="btn btn-ghost btn-sm" data-bs-toggle="dropdown">
              <i className="fas fa-ellipsis"></i>
            </button>
            <ul className="dropdown-menu dropdown-menu-end shell">
              <li><a className="dropdown-item" href={urls.edit_items}>
                <i className="fas fa-pen"></i>{t('menu.edit_items', 'Edit items')}</a></li>
              <li><a className="dropdown-item" href={urls.edit_user}>
                <i className="fas fa-user-pen"></i>{t('menu.change_user', 'Change user')}</a></li>
              <li><a className="dropdown-item" href={urls.edit_period}>
                <i className="fas fa-calendar-days"></i>{t('menu.edit_period', 'Edit period')}</a></li>
              <li><hr className="dropdown-divider" /></li>
              <li><a className="dropdown-item" href={urls.resend_email}>
                <i className="fas fa-envelope"></i>{t('menu.resend_email', 'Resend confirmation')}</a></li>
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
    </>
  );
}

/* ---------- Tabs + contents ---------- */
function RentalTabs({ rental, items, rooms, issues, history, urls }) {
  const [tab, setTab] = React.useState('items');
  const [expanded, setExpanded] = React.useState(null);

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
        <div className="surface" style={{padding: 0, overflow: 'hidden'}}>
          {items.map(item => (
            <ItemRow key={item.id} item={item}
                     expanded={expanded === item.id}
                     toggle={() => setExpanded(expanded === item.id ? null : item.id)}
                     urls={urls} />
          ))}
          <div style={{padding: '10px 14px', background:'var(--bg-sub)', borderTop: '1px solid var(--line)',
                          fontSize: 12, display:'flex', alignItems:'center', gap: 10}}>
            <span className="muted">
              {t('items.total', 'Total:')} {items.length} · {items.reduce((a, i) => a + (i.qty_issued || 0), 0)} {t('items.units_issued', 'units issued')}
            </span>
            <a className="btn btn-ghost btn-sm ms-auto" href={urls.edit_items}>
              <i className="fas fa-plus me-1"></i>{t('btn.add_item', 'Add item')}
            </a>
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
        <IssuesPanel issues={issues} urls={urls} />
      )}

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

/* ---------- Item row with expand ---------- */
function ItemRow({ item, expanded, toggle, urls }) {
  const fullyReturned = (item.qty_returned || 0) >= (item.qty_issued || 0);
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
        <button className="btn btn-ghost btn-sm" onClick={(e)=>e.stopPropagation()}>
          <i className="fas fa-ellipsis muted"></i>
        </button>
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
            <a className="btn btn-ghost btn-sm" href={urls.swap_unit + '?item=' + item.id}>
              <i className="fas fa-arrow-right-arrow-left me-1"></i>{t('btn.swap', 'Swap unit')}
            </a>
            <a className="btn btn-ghost btn-sm" href={urls.remove_item + '?item=' + item.id}>
              <i className="fas fa-circle-minus me-1"></i>{t('btn.remove', 'Remove from rental')}
            </a>
            <a className="btn btn-ghost btn-sm" href={urls.report_issue + '?item=' + item.id}>
              <i className="fas fa-triangle-exclamation me-1"></i>{t('btn.report_issue', 'Report issue')}
            </a>
          </div>
        </div>
      )}
    </>
  );
}

/* ---------- Issues tab ---------- */
function IssuesPanel({ issues, urls }) {
  return (
    <>
      <div style={{display:'flex', alignItems:'center', marginBottom: 10, gap: 10}}>
        <div className="muted tiny">
          {t('issues.note', "Issues are logged during return — they don't affect item availability until closed.")}
        </div>
        <a className="btn btn-ghost btn-sm ms-auto" href={urls.report_issue}>
          <i className="fas fa-plus me-1"></i>{t('btn.log_issue', 'Log issue')}
        </a>
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
            <button className="btn btn-ghost btn-sm"><i className="fas fa-ellipsis muted"></i></button>
          </div>
        ))}
      </div>
    </>
  );
}

Object.assign(window, { ActionBar, RentalTabs });
