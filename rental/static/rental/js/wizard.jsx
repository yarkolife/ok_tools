/* =========================================================
   rental/static/rental/js/wizard.jsx
   4-step rental creation wizard + Quick mode.
   Adapted from prototype screen-wizard.jsx — all mock data
   now comes from Django via props (`initial`).
   Depends on: shared.jsx (cls, fmtDate, apiPost, apiGet, t, Avatar)
   ========================================================= */

/* ===== Root ===== */
function WizardScreen({ initial }) {
  // initial = {
  //   categories:  [{id, label, icon, count}, ...],
  //   users:       [{id, name, org, role, initials, past, warn?}, ...],
  //   rooms:       [{id, name, sub, free}, ...],
  //   urls: { create, quick_issue, inventory_search, availability_check, users_search },
  //   defaults: { from, to, project, purpose }
  // }

  const [mode, setMode] = React.useState('wizard');
  const [step, setStep] = React.useState(0);
  const [submitting, setSubmitting] = React.useState(false);

  const [cart, setCart]   = React.useState([]);
  const [rooms, setRooms] = React.useState([]);
  const [user, setUser]   = React.useState(null);
  const [period, setPeriod] = React.useState({
    from: initial.defaults?.from || '',
    to:   initial.defaults?.to   || '',
  });
  const [project, setProject] = React.useState(initial.defaults?.project || '');
  const [purpose, setPurpose] = React.useState(initial.defaults?.purpose || '');
  const [notifyEmail, setNotifyEmail] = React.useState(true);
  const [notifySms, setNotifySms]     = React.useState(false);

  const steps = [
    { title: t('wiz.step1', 'User'),               hint: user ? user.name : t('wiz.no_user', 'Not selected') },
    { title: t('wiz.step2', 'Time & conflicts'),   hint: period.from ? period.from.slice(0,10) + ' → ' + period.to.slice(0,10) : '—' },
    { title: t('wiz.step3', 'Items & rooms'),      hint: `${cart.length} ${t('wiz.items','items')} · ${rooms.length} ${t('wiz.rooms','rooms')}` },
    { title: t('wiz.step4', 'Review & confirm'),   hint: t('wiz.send_confirm', 'Send confirmation') },
  ];

  // Validation per step — block "Next" until required fields are set
  const canNext = () => {
    if (step === 0) return !!user;
    if (step === 1) {
      const f = new Date(period.from), tt = new Date(period.to);
      return !isNaN(f) && !isNaN(tt) && f < tt;
    }
    if (step === 2) return cart.length > 0 || rooms.length > 0;
    return true;
  };

  const submit = async () => {
    setSubmitting(true);
    try {
      const payload = {
        user_id: user?.id,
        from: period.from,
        to: period.to,
        project, purpose,
        items: cart.map(c => ({ id: c.id, qty: c.qty })),
        rooms: rooms.map(r => ({ id: r.id, slot: r.slot })),
        notify: { email: notifyEmail, sms: notifySms },
      };
      const res = await apiPost(initial.urls.create, payload);
      window.location = res.detail_url;
    } catch (e) {
      alert(t('err.create', 'Could not create rental: ') + e.message);
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="page-title">
        <h1>{t('wiz.title', 'Create rental')}</h1>
        <span className="sub">{t('wiz.sub', 'Reserve items and rooms for a user')}</span>
        <div className="page-actions">
          <div className="btn-group" role="group">
            <button type="button" className={cls('btn btn-sm', mode === 'wizard' ? 'btn-primary' : 'btn-ghost')}
                    onClick={() => setMode('wizard')}>
              <i className="fas fa-list-ol me-1"></i>{t('wiz.guided', 'Guided')}
            </button>
            <button type="button" className={cls('btn btn-sm', mode === 'quick' ? 'btn-primary' : 'btn-ghost')}
                    onClick={() => setMode('quick')}>
              <i className="fas fa-bolt me-1"></i>{t('wiz.quick', 'Quick')}
            </button>
          </div>
        </div>
      </div>

      {mode === 'quick'
        ? <QuickRental initial={initial} cart={cart} setCart={setCart}
                       user={user} setUser={setUser} period={period} setPeriod={setPeriod} />
        : <>
            <Stepper steps={steps} active={step} setActive={setStep} />

            <div className="wizard-body">
              {step === 0 && <StepUser initial={initial} selected={user} setSelected={setUser} />}
              {step === 1 && <StepTime initial={initial} period={period} setPeriod={setPeriod} cart={cart} />}
              {step === 2 && <StepItems initial={initial} cart={cart} setCart={setCart}
                                        rooms={rooms} setRooms={setRooms} />}
              {step === 3 && <StepReview user={user} period={period} cart={cart} rooms={rooms}
                                         project={project} setProject={setProject}
                                         purpose={purpose} setPurpose={setPurpose}
                                         notifyEmail={notifyEmail} setNotifyEmail={setNotifyEmail}
                                         notifySms={notifySms} setNotifySms={setNotifySms} />}
            </div>

            <div className="wizard-foot">
              <button className="btn btn-ghost btn-sm" disabled={step === 0} onClick={() => setStep(step - 1)}>
                <i className="fas fa-arrow-left me-1"></i>{t('btn.back', 'Back')}
              </button>
              <div className="progress-text">
                {t('wiz.step', 'Step')} {step + 1} {t('wiz.of', 'of')} {steps.length}
              </div>
              {step < steps.length - 1
                ? <button className="btn btn-primary btn-sm" disabled={!canNext()}
                          onClick={() => setStep(step + 1)}>
                    {t('btn.next', 'Next')} <i className="fas fa-arrow-right ms-1"></i>
                  </button>
                : <button className="btn btn-primary btn-sm" disabled={submitting} onClick={submit}>
                    <i className="fas fa-check me-1"></i>
                    {submitting ? t('btn.sending', 'Sending…') : t('btn.confirm_send', 'Confirm & send')}
                  </button>}
            </div>
          </>
      }
    </>
  );
}

/* ===== Stepper ===== */
function Stepper({ steps, active, setActive }) {
  return (
    <div className="stepper">
      {steps.map((s, i) => (
        <div key={i}
             className={cls('step', i === active && 'active', i < active && 'done')}
             onClick={() => setActive(i)}>
          <div className="step-num">
            {i < active ? <i className="fas fa-check" style={{fontSize: 11}}></i> : i + 1}
          </div>
          <div className="step-body">
            <div className="step-title">{s.title}</div>
            <div className="step-hint">{s.hint}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ===== STEP 1 — Items & rooms ===== */
function StepItems({ initial, cart, setCart, rooms, setRooms }) {
  const [activeTab, setActiveTab] = React.useState(initial.categories[0]?.id || '');
  const [mode, setMode] = React.useState('items');
  const [search, setSearch] = React.useState('');
  const [items, setItems] = React.useState([]);
  const [loading, setLoading] = React.useState(false);

  // Fetch inventory items when category or search changes
  React.useEffect(() => {
    if (mode !== 'items' || activeTab == null) return;
    setLoading(true);
    const timer = setTimeout(() => {
      const q = new URLSearchParams({ cat: activeTab, q: search });
      apiGet(`${initial.urls.inventory_search}?${q}`)
        .then(data => setItems(data.items || []))
        .catch(() => setItems([]))
        .finally(() => setLoading(false));
    }, search ? 250 : 0);
    return () => clearTimeout(timer);
  }, [activeTab, search, mode]);

  const inCart = id => cart.some(c => c.id === id);
  const addItem = it => !inCart(it.id) && setCart(c => [...c, { id: it.id, name: it.name, num: it.num, qty: 1, cat: it.cat }]);
  const setQty = (id, qty) => setCart(c => c.map(x => x.id === id ? { ...x, qty } : x));
  const removeItem = id => setCart(c => c.filter(x => x.id !== id));

  return (
    <div>
      <div className="d-flex align-items-center mb-3" style={{gap: 12}}>
        <h2 style={{fontSize: 16, fontWeight: 600, margin: 0}}>
          {t('wiz.what_need', 'What do you need?')}
        </h2>
        <div className="muted tiny">{t('wiz.tap_to_add', 'Tap to add. Then set quantities on the right.')}</div>
        <div className="ms-auto d-flex" style={{gap: 4}}>
          <button className={cls('btn btn-sm', mode === 'items' ? 'btn-primary' : 'btn-ghost')}
                  onClick={() => setMode('items')}>
            <i className="fas fa-toolbox me-1"></i>{t('wiz.equipment', 'Equipment')}
          </button>
          <button className={cls('btn btn-sm', mode === 'rooms' ? 'btn-primary' : 'btn-ghost')}
                  onClick={() => setMode('rooms')}>
            <i className="fas fa-door-open me-1"></i>{t('wiz.rooms', 'Reserve rooms')}
          </button>
        </div>
      </div>

      {mode === 'items' ? (
        <div className="catalog" style={{border: '1px solid var(--line)', borderRadius: 12, overflow: 'hidden', background: '#fff'}}>
          <div className="catalog-tabs">
            {initial.categories.map(c => (
              <div key={c.id} className={cls('t', activeTab === c.id && 'active')}
                   onClick={() => setActiveTab(c.id)}>
                <i className={`fas ${c.icon}`}></i>
                <span>{c.label}</span>
                <span className="count">{c.count}</span>
              </div>
            ))}
          </div>
          <div className="catalog-body">
            <div className="filters">
              <div className="search">
                <i className="fas fa-search"></i>
                <input type="text" className="form-control" placeholder={t('wiz.search_items', 'Search items…')}
                       value={search} onChange={e => setSearch(e.target.value)} />
              </div>
              <div className="ms-auto muted tiny">
                {loading ? t('loading', 'Loading…') : `${items.length} ${t('wiz.in_cat', 'in category')}`}
              </div>
            </div>

            {items.map(item => {
              const chosen = inCart(item.id);
              return (
                <div key={item.id}
                     className={cls('item-row', chosen && 'selected', item.conflict && !chosen && 'conflict')}
                     onClick={() => addItem(item)}>
                  <input type="checkbox" className="form-check-input" checked={chosen} readOnly />
                  <div>
                    <div className="name">{item.name}</div>
                    <div className="num">{item.num} · <span className="muted">{item.loc}</span></div>
                  </div>
                  <div className="meta">{item.qty.avail}/{item.qty.total} {t('wiz.available', 'available')}</div>
                  <div>
                    {item.conflict
                      ? <span className="tag tag-bad"><i className="fas fa-triangle-exclamation" style={{fontSize: 9}}></i>{t('tag.conflict','Conflict')}</span>
                      : item.qty.avail > 0
                        ? <span className="tag tag-ok">{t('tag.in_stock', 'In stock')}</span>
                        : <span className="tag tag-warn">{t('tag.out', 'Out')}</span>}
                  </div>
                  <div className="meta" style={{textAlign: 'right'}}>
                    {item.qty.reserved ? `${item.qty.reserved} ${t('wiz.reserved','reserved')}` : t('wiz.free','Free')}
                  </div>
                  <div style={{textAlign: 'right'}}>
                    <button className="btn btn-sm btn-ghost"
                            onClick={e => { e.stopPropagation(); chosen ? removeItem(item.id) : addItem(item); }}>
                      <i className={`fas fa-${chosen ? 'minus' : 'plus'}`}></i>
                    </button>
                  </div>
                </div>
              );
            })}
            {!loading && items.length === 0 && (
              <div className="muted p-3">{t('wiz.no_items', 'No items match.')}</div>
            )}
          </div>
        </div>
      ) : (
        <RoomPicker rooms={rooms} setRooms={setRooms} options={initial.rooms || []} />
      )}

      <CartSummary cart={cart} setQty={setQty} removeItem={removeItem} rooms={rooms} />
    </div>
  );
}

function RoomPicker({ rooms, setRooms, options }) {
  const toggle = r => {
    if (rooms.find(x => x.id === r.id)) setRooms(rs => rs.filter(x => x.id !== r.id));
    else setRooms(rs => [...rs, { id: r.id, name: r.name, slot: r.default_slot || '' }]);
  };
  return (
    <div className="surface" style={{padding: 14}}>
      <div className="row g-2">
        {options.map(r => {
          const on = rooms.find(x => x.id === r.id);
          return (
            <div key={r.id} className="col-md-6">
              <div className={cls('user-card', on && 'selected')} onClick={() => toggle(r)}
                   style={{gridTemplateColumns: '36px 1fr auto'}}>
                <span className="av" style={{width: 36, height: 36, fontSize: 14}}>
                  <i className="fas fa-door-open"></i>
                </span>
                <div><div className="name">{r.name}</div><div className="org">{r.sub}</div></div>
                {r.free
                  ? (on ? <span className="tag tag-hold">{t('room.added','Added')}</span>
                        : <span className="tag tag-ok">{t('room.open','Open')}</span>)
                  : <span className="tag tag-warn">{t('room.restricted','Restricted')}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CartSummary({ cart, setQty, removeItem, rooms }) {
  if (cart.length === 0 && rooms.length === 0) return null;
  return (
    <div className="surface" style={{marginTop: 14, padding: '12px 14px'}}>
      <div className="d-flex align-items-center mb-2" style={{gap: 8}}>
        <strong style={{fontSize: 13}}>{t('cart.title', 'In this rental')}</strong>
        <span className="muted tiny">{cart.length} {t('wiz.items', 'items')} · {rooms.length} {t('wiz.rooms', 'rooms')}</span>
      </div>
      {cart.map(c => (
        <div key={c.id} style={{display: 'grid', gridTemplateColumns: '1fr 120px 34px', gap: 10, alignItems: 'center',
                                   padding: '8px 0', borderBottom: '1px solid var(--line)', fontSize: 13}}>
          <div>
            <div style={{fontWeight: 500}}>{c.name}</div>
            <div className="muted mono" style={{fontSize: 11}}>{c.num} · {c.cat}</div>
          </div>
          <div className="input-group input-group-sm" style={{maxWidth: 110}}>
            <button className="btn btn-ghost" onClick={() => setQty(c.id, Math.max(1, c.qty - 1))}>−</button>
            <input className="form-control text-center" value={c.qty} readOnly />
            <button className="btn btn-ghost" onClick={() => setQty(c.id, c.qty + 1)}>+</button>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => removeItem(c.id)}>
            <i className="fas fa-times muted"></i>
          </button>
        </div>
      ))}
      {rooms.map(r => (
        <div key={r.id} style={{display: 'flex', gap: 10, alignItems: 'center', padding: '8px 0',
                                   borderBottom: '1px solid var(--line)', fontSize: 13}}>
          <i className="fas fa-door-open muted"></i>
          <div>
            <div style={{fontWeight: 500}}>{r.name}</div>
            <div className="muted tiny">{r.slot}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ===== STEP 2 — User ===== */
function StepUser({ initial, selected, setSelected }) {
  const [q, setQ] = React.useState('');
  const [remoteUsers, setRemoteUsers] = React.useState([]);
  const [loading, setLoading] = React.useState(false);

  // Debounced remote search when user types
  React.useEffect(() => {
    if (!q || q.length < 2) { setRemoteUsers([]); return; }
    setLoading(true);
    const timer = setTimeout(() => {
      apiGet(initial.urls.users_search + '?q=' + encodeURIComponent(q))
        .then(data => setRemoteUsers(data.users || []))
        .catch(() => setRemoteUsers([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [q]);

  // Merge local + remote, deduplicate by id
  const localFiltered = (initial.users || []).filter(u =>
    !q || u.name.toLowerCase().includes(q.toLowerCase()) || u.org.toLowerCase().includes(q.toLowerCase())
  );
  const seen = new Set(localFiltered.map(u => u.id));
  const merged = [...localFiltered, ...(remoteUsers || []).filter(u => !seen.has(u.id))];

  return (
    <div>
      <h2 style={{fontSize: 16, fontWeight: 600, margin: '0 0 4px'}}>
        {t('wiz.who', 'Who is this rental for?')}
      </h2>
      <div className="muted tiny" style={{marginBottom: 14}}>
        {t('wiz.who_sub', 'Pick an existing user or create a new account.')}
      </div>
      <div className="filters" style={{marginBottom: 12}}>
        <div className="search" style={{maxWidth: 420}}>
          <i className="fas fa-search"></i>
          <input type="text" className="form-control"
                 placeholder={t('wiz.search_user', 'Search by name, email, student ID…')}
                 value={q} onChange={e => setQ(e.target.value)} />
        </div>
        <a className="btn btn-ghost btn-sm" href={initial.urls.new_user} target="_blank">
          <i className="fas fa-user-plus me-1"></i>{t('wiz.new_user', 'New user')}
        </a>
      </div>
      {loading && <div className="muted tiny" style={{marginBottom: 8}}>{t('loading', 'Searching…')}</div>}
      <div className="row g-2">
        {merged.map(u => (
          <div key={u.id} className="col-md-6">
            <div className={cls('user-card', selected?.id === u.id && 'selected')}
                 onClick={() => setSelected(u)}>
              <Avatar user={u} size={32} />
              <div style={{minWidth: 0}}>
                <div className="name">{u.name}</div>
                <div className="org">{u.org} · {u.role} · {u.past || 0} {t('user.past_rentals','past rentals')}</div>
                {u.warn && <div className="mt-1 tiny" style={{color: 'oklch(0.45 0.14 28)'}}>
                  <i className="fas fa-triangle-exclamation me-1"></i>{u.warn}
                </div>}
              </div>
              {selected?.id === u.id && <i className="fas fa-check" style={{color: 'var(--brand)'}}></i>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ===== STEP 3 — Time & conflicts ===== */
function StepTime({ initial, period, setPeriod, cart }) {
  const [conflicts, setConflicts] = React.useState([]);
  const [loading, setLoading] = React.useState(false);

  // Pull real conflict data whenever period or cart changes.
  React.useEffect(() => {
    if (!period.from || !period.to || cart.length === 0) { setConflicts([]); return; }
    setLoading(true);
    const timer = setTimeout(() => {
      apiPost(initial.urls.availability_check, {
        from: period.from, to: period.to, items: cart.map(c => c.id),
      }).then(d => setConflicts(d.rows || []))
        .catch(() => setConflicts([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [period.from, period.to, cart]);

  const from = new Date(period.from), to = new Date(period.to);
  const warnings = [];
  if (period.from && period.to && from >= to) warnings.push(t('wiz.warn.reversed', 'End time is before start time.'));

  // Check against configured working hours
  const wh = initial.working_hours || {};
  if (period.from) {
    const dayKey = String(from.getDay() === 0 ? 6 : from.getDay() - 1); // JS getDay: 0=Sun, config: 0=Mon
    const dayHours = wh[dayKey];
    if (dayHours && !dayHours.enabled) {
      warnings.push(t('wiz.warn.closed', 'Selected day is closed.'));
    } else if (dayHours && dayHours.enabled) {
      const h = from.getHours();
      const m = from.getMinutes();
      const startParts = (dayHours.start || '00:00').split(':').map(Number);
      const endParts = (dayHours.end || '00:00').split(':').map(Number);
      const startMins = startParts[0] * 60 + startParts[1];
      const endMins = endParts[0] * 60 + endParts[1];
      const pickMins = h * 60 + m;
      if (pickMins < startMins || pickMins >= endMins) {
        warnings.push(t('wiz.warn.hours', 'Pickup is outside working hours ({start} – {end}).').replace('{start}', dayHours.start).replace('{end}', dayHours.end));
      }
    }
  }
  const duration = period.from && period.to ? Math.round((to - from) / 36e5) : 0;
  const hasConflict = conflicts.some(c => c.ranges && c.ranges.some(r => r.conflict));

  return (
    <div>
      <h2 style={{fontSize: 16, fontWeight: 600, margin: '0 0 4px'}}>
        {t('wiz.when', 'When is the equipment needed?')}
      </h2>
      <div className="muted tiny" style={{marginBottom: 14}}>
        {(() => {
          const wh = initial.working_hours || {};
          const days = [];
          for (let i = 0; i < 7; i++) {
            const d = wh[String(i)];
            if (d && d.enabled) days.push(d.short_label);
          }
          const hours = Object.values(wh).filter(d => d.enabled).map(d => d.start + '–' + d.end);
          const uniqueHours = [...new Set(hours)].join(', ');
          return t('wiz.hours', 'Working hours: {days} {hours}').replace('{days}', days.join('–')).replace('{hours}', uniqueHours);
        })()}
      </div>

      <div className="time-grid" style={{marginBottom: 14}}>
        <div className="t-card">
          <label>{t('wiz.pickup', 'Pickup')}</label>
          <input type="datetime-local" className="form-control" value={period.from} step="1800"
                 onChange={e => setPeriod(p => ({...p, from: e.target.value}))} />
        </div>
        <div className="t-card">
          <label>{t('wiz.return_by', 'Return by')}</label>
          <input type="datetime-local" className="form-control" value={period.to} step="1800"
                 onChange={e => setPeriod(p => ({...p, to: e.target.value}))} />
          <div className="tiny muted mt-1">
            <i className="fas fa-clock me-1"></i>{duration > 0 ? `${duration}h` : '—'}
          </div>
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="inline-extend" style={{background: 'oklch(0.97 0.04 28)', borderColor: 'oklch(0.85 0.09 28)'}}>
          <i className="fas fa-triangle-exclamation" style={{color: 'oklch(0.55 0.16 28)'}}></i>
          <ul style={{margin: 0, paddingLeft: 16, color: 'oklch(0.35 0.12 28)'}}>
            {warnings.map((w, i) => <li key={i} style={{fontSize: 12}}>{w}</li>)}
          </ul>
        </div>
      )}

      {conflicts.length > 0 && (
        <div className="availability">
          <div className="d-flex align-items-center" style={{gap: 10, marginBottom: 10}}>
            <strong style={{fontSize: 13}}>{t('wiz.availability', 'Availability — selected period')}</strong>
            {hasConflict
              ? <span className="tag tag-bad"><i className="fas fa-exclamation"></i>{t('wiz.conflicts', 'Conflicts')}</span>
              : <span className="tag tag-ok">{t('wiz.clear', 'All clear')}</span>}
            {loading && <span className="muted tiny ms-auto">{t('loading', 'Loading…')}</span>}
          </div>
          <div style={{display: 'grid', gridTemplateColumns: '180px 1fr', gap: 10, alignItems: 'center', fontSize: 12}}>
            {conflicts.map((row, i) => (
              <React.Fragment key={i}>
                <div style={{fontSize: 12.5, color: 'var(--ink-2)', fontWeight: 500}}>{row.item}</div>
                <div className="timeline-track">
                  {row.selection && (
                    <div className="timeline-block selection"
                         style={{left: `${row.selection.left}%`, width: `${row.selection.width}%`}}>
                      {t('wiz.your_booking', 'Your booking')}
                    </div>
                  )}
                  {(row.ranges || []).map((r, j) => (
                    <div key={j} className="timeline-block"
                         style={{left: `${r.left}%`, width: `${r.width}%`}}
                         title={r.label}>{r.label}</div>
                  ))}
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ===== STEP 4 — Review + email preview ===== */
function StepReview({ user, period, cart, rooms, project, setProject, purpose, setPurpose,
                     notifyEmail, setNotifyEmail, notifySms, setNotifySms }) {
  if (!user) return <div className="muted">{t('wiz.need_user','Select a user first.')}</div>;
  return (
    <div className="row g-4">
      <div className="col-lg-6">
        <h2 style={{fontSize: 16, fontWeight: 600, margin: '0 0 10px'}}>
          {t('wiz.confirm', 'Confirm details')}
        </h2>

        <div className="surface p-3 mb-3">
          <div className="muted tiny" style={{textTransform: 'uppercase', fontWeight: 600, letterSpacing: '.04em', marginBottom: 6}}>
            {t('wiz.project', 'Project')}
          </div>
          <input className="form-control" value={project} onChange={e => setProject(e.target.value)}
                 placeholder={t('wiz.project_ph', 'Project name')}
                 style={{fontSize: 15, fontWeight: 600}} />
          <textarea className="form-control mt-2" rows={2} value={purpose}
                    onChange={e => setPurpose(e.target.value)}
                    placeholder={t('wiz.purpose_ph', 'Short description of purpose')} />
        </div>

        <div className="surface p-3 mb-3">
          <strong style={{fontSize: 13}}>{t('wiz.user', 'User')}</strong>
          <div className="d-flex mt-2" style={{gap: 10, alignItems: 'center'}}>
            <Avatar user={user} size={36} />
            <div>
              <div style={{fontWeight: 600, fontSize: 13}}>{user.name}</div>
              <div className="muted tiny">{user.org} · {user.role}</div>
            </div>
          </div>
        </div>

        <div className="surface p-3 mb-3">
          <strong style={{fontSize: 13}}>{t('wiz.period', 'Period')}</strong>
          <div style={{display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 10, alignItems: 'center',
                        fontSize: 13, marginTop: 8}}>
            <div>
              <div className="muted tiny">{t('wiz.pickup', 'Pickup')}</div>
              <div style={{fontWeight: 600}}>{fmtDate(period.from.replace('T', ' '))}</div>
            </div>
            <i className="fas fa-arrow-right muted"></i>
            <div>
              <div className="muted tiny">{t('wiz.return', 'Return')}</div>
              <div style={{fontWeight: 600}}>{fmtDate(period.to.replace('T', ' '))}</div>
            </div>
          </div>
        </div>

        <div className="surface p-3 mb-3">
          <strong style={{fontSize: 13}}>{t('wiz.items_rooms', 'Items & rooms')}</strong>
          <ul style={{margin: 8, paddingLeft: 0, listStyle: 'none', fontSize: 13}}>
            {cart.map(c => (
              <li key={c.id} style={{display: 'flex', justifyContent: 'space-between', padding: '4px 0',
                                        borderBottom: '1px solid var(--line)'}}>
                <span>{c.name}</span><span className="muted">× {c.qty}</span>
              </li>
            ))}
            {rooms.map(r => (
              <li key={r.id} style={{display: 'flex', justifyContent: 'space-between', padding: '4px 0',
                                        borderBottom: '1px solid var(--line)'}}>
                <span><i className="fas fa-door-open me-2 muted"></i>{r.name}</span>
                <span className="muted">{r.slot}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="surface p-3">
          <strong style={{fontSize: 13}}>{t('wiz.notifications', 'Notifications')}</strong>
          <div className="form-check mt-2">
            <input className="form-check-input" type="checkbox" checked={notifyEmail}
                   onChange={e => setNotifyEmail(e.target.checked)} id="nEmail" />
            <label className="form-check-label tiny" htmlFor="nEmail">
              {t('wiz.notify_email', 'Send confirmation email to')} <strong>{user.email}</strong>
            </label>
          </div>
          <div className="form-check">
            <input className="form-check-input" type="checkbox" checked={notifySms}
                   onChange={e => setNotifySms(e.target.checked)} id="nSms" />
            <label className="form-check-label tiny" htmlFor="nSms">
              {t('wiz.notify_sms', 'Send SMS pickup reminder 1h before')}
            </label>
          </div>
        </div>
      </div>

      <div className="col-lg-6">
        <strong style={{fontSize: 13}}>{t('wiz.email_preview', 'Confirmation email preview')}</strong>
        <div className="email-preview mt-2">
          <div className="email-head">
            <div className="row">
              <div className="lbl">From</div><div>workshop@uni.de</div>
              <div className="lbl">To</div><div>{user.email}</div>
              <div className="lbl">Subject</div><div>{t('wiz.email_subject', 'Your rental — confirmed')}</div>
            </div>
          </div>
          <div className="email-body">
            <h3>{t('wiz.email_hi', 'Hi')} {user.name.split(' ')[0]},</h3>
            <p>{t('wiz.email_intro', 'Your workshop rental is reserved. Please pick up at the front desk at the time below.')}</p>
            {project && (
              <p style={{background: 'var(--bg-sub)', padding: '10px 12px', borderRadius: 8,
                            borderLeft: '3px solid var(--brand)'}}>
                <strong>{project}</strong><br/><span className="muted">{purpose}</span>
              </p>
            )}
            <table>
              <tbody>
                <tr><th>{t('wiz.pickup', 'Pickup')}</th><td>{fmtDate(period.from.replace('T', ' '))}</td></tr>
                <tr><th>{t('wiz.return_by', 'Return by')}</th><td>{fmtDate(period.to.replace('T', ' '))}</td></tr>
              </tbody>
            </table>
            <p style={{marginTop: 10, marginBottom: 4}}>
              <strong>{t('wiz.items_n', 'Items')} ({cart.reduce((a, c) => a + c.qty, 0)})</strong>
            </p>
            <table>
              <tbody>
                {cart.map(c => (
                  <tr key={c.id}>
                    <td>{c.name} <span className="muted mono" style={{fontSize: 11}}>({c.num})</span></td>
                    <td style={{textAlign: 'right', width: 60}}>{c.qty}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ===== Quick mode ===== */
function QuickRental({ initial, cart, setCart, user, setUser, period, setPeriod }) {
  const [scan, setScan] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  const addByScan = async () => {
    if (!scan.trim()) return;
    try {
      const data = await apiGet(`${initial.urls.inventory_search}?num=${encodeURIComponent(scan.trim())}`);
      const hit = data.items?.[0];
      if (hit) {
        setCart(c => c.some(x => x.id === hit.id) ? c : [...c, { ...hit, qty: 1 }]);
      } else {
        alert(t('err.scan_not_found', 'Inventory code not found: ') + scan);
      }
    } catch (e) { alert(e.message); }
    setScan('');
  };

  const issueNow = async () => {
    if (!user || cart.length === 0) return;
    setBusy(true);
    try {
      const r = await apiPost(initial.urls.quick_issue, {
        user_id: user.id, from: period.from, to: period.to,
        items: cart.map(c => ({ id: c.id, qty: c.qty })),
      });
      window.location = r.detail_url;
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div>
      <div className="quick-panel">
        <div className="quick-row">
          <div>
            <div className="muted tiny mb-1" style={{textTransform: 'uppercase', fontWeight: 600}}>{t('wiz.user','User')}</div>
            <select className="form-select form-select-sm" value={user?.id || ''}
                    onChange={e => setUser(initial.users.find(u => String(u.id) === e.target.value))}>
              <option value="">—</option>
              {initial.users.map(u => <option key={u.id} value={u.id}>{u.name} — {u.org}</option>)}
            </select>
          </div>
          <div>
            <div className="muted tiny mb-1" style={{textTransform: 'uppercase', fontWeight: 600}}>{t('wiz.pickup','Pickup')}</div>
            <input type="datetime-local" className="form-control form-control-sm"
                   value={period.from} onChange={e => setPeriod(p => ({...p, from: e.target.value}))} />
          </div>
          <div>
            <div className="muted tiny mb-1" style={{textTransform: 'uppercase', fontWeight: 600}}>{t('wiz.return_by','Return by')}</div>
            <input type="datetime-local" className="form-control form-control-sm"
                   value={period.to} onChange={e => setPeriod(p => ({...p, to: e.target.value}))} />
          </div>
          <div>
            <div className="muted tiny mb-1" style={{textTransform: 'uppercase', fontWeight: 600}}>{t('wiz.scan','Scan')}</div>
            <div className="input-group input-group-sm">
              <span className="input-group-text"><i className="fas fa-barcode"></i></span>
              <input className="form-control" placeholder="INV-…"
                     value={scan} onChange={e => setScan(e.target.value)}
                     onKeyDown={e => e.key === 'Enter' && addByScan()} />
            </div>
          </div>
          <div>
            <button className="btn btn-primary btn-sm" disabled={busy || !user || cart.length === 0} onClick={issueNow}>
              <i className="fas fa-check me-1"></i>{t('btn.issue_now', 'Issue now')}
            </button>
          </div>
        </div>
      </div>

      <div className="surface p-0">
        {cart.map((c, i) => (
          <div key={c.id} style={{display: 'grid', gridTemplateColumns: '28px 1fr 100px 60px', gap: 10,
                                     padding: '10px 14px', borderBottom: '1px solid var(--line)', alignItems: 'center',
                                     fontSize: 13}}>
            <div className="muted mono">{i + 1}</div>
            <div>
              <div style={{fontWeight: 500}}>{c.name}</div>
              <div className="muted tiny mono">{c.num}</div>
            </div>
            <div className="mono">× {c.qty}</div>
            <button className="btn btn-ghost btn-sm"
                    onClick={() => setCart(cc => cc.filter(x => x.id !== c.id))}>
              <i className="fas fa-times muted"></i>
            </button>
          </div>
        ))}
        {cart.length === 0 && (
          <div className="muted p-3 text-center">
            {t('wiz.scan_hint', 'Scan or enter an inventory code above to add items.')}
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { WizardScreen });
