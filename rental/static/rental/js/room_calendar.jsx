const { useState, useEffect, useMemo } = React;

/* Booking config of the page: {urls: {create, users_search, new_user}}. */
const __roomCalCfgNode = document.getElementById('room-cal-config');
const ROOM_CAL_CFG = __roomCalCfgNode ? JSON.parse(__roomCalCfgNode.textContent) : null;

function RoomCalendar({ date }) {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dayInfo, setDayInfo] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  // Drag over free slots: {roomId, anchor, cur} (slot indexes).
  const [drag, setDrag] = useState(null);
  // Open booking dialog: {room, start, end} (slot indexes, end exclusive).
  const [booking, setBooking] = useState(null);
  const canBook = !!(ROOM_CAL_CFG && ROOM_CAL_CFG.urls && ROOM_CAL_CFG.urls.create);

  // Finish a drag wherever the mouse is released.
  useEffect(() => {
    if (!drag) return;
    const onUp = () => {
      const room = rooms.find(r => r.id === drag.roomId);
      if (room) {
        setBooking({
          room,
          start: Math.min(drag.anchor, drag.cur),
          end: Math.max(drag.anchor, drag.cur) + 1,
        });
      }
      setDrag(null);
    };
    document.addEventListener('mouseup', onUp);
    return () => document.removeEventListener('mouseup', onUp);
  }, [drag, rooms]);

  useEffect(() => {
    async function fetchSchedule() {
      try {
        setLoading(true);
        setError(null);
        const url = `/rental/api/room-schedule/?start_date=${date}&end_date=${date}`;
        const response = await fetch(url, { credentials: 'same-origin' });
        if (!response.ok) {
          if (response.status === 302 || response.status === 403) {
            throw new Error(t('auth_required', 'Please log in to view the schedule'));
          }
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        if (data.success) {
          setRooms(data.rooms || []);
          const firstSchedule = data.rooms && data.rooms[0] && data.rooms[0].schedule && data.rooms[0].schedule[0];
          if (firstSchedule) {
            setDayInfo({
              is_closed: firstSchedule.is_closed || false,
              working_hours: firstSchedule.working_hours || null,
              day_name: firstSchedule.day_name,
              day_short: firstSchedule.day_short,
            });
          }
        } else {
          throw new Error(data.error || 'Unknown error');
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchSchedule();
  }, [date, reloadKey]);

  if (loading && rooms.length === 0) {
    return (
      <div className="tl-loading">
        <i className="fas fa-spinner fa-spin"></i>
        <span>{t('loading', 'Loading...')}</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tl-error">
        <i className="fas fa-circle-exclamation"></i>
        <span>{t('error_loading', 'Failed to load room schedule')}: {error}</span>
      </div>
    );
  }

  if (rooms.length === 0) {
    return (
      <div className="tl-empty">
        <i className="fas fa-door-closed"></i>
        <span>{t('no_rooms', 'No rooms found. Add rooms in admin.')}</span>
      </div>
    );
  }

  if (dayInfo && dayInfo.is_closed) {
    return (
      <div className="tl-closed">
        <i className="fas fa-moon"></i>
        <span>{dayInfo.day_name} — {t('closed_day', 'Closed')}</span>
      </div>
    );
  }

  const totalSlots = rooms[0]?.schedule?.[0]?.slots?.length || 0;

  return (
    <div className="tl-wrap">
      {dayInfo && dayInfo.working_hours && dayInfo.working_hours.start && (
        <div className="tl-wh">
          <i className="fas fa-clock"></i>
          {dayInfo.working_hours.start} — {dayInfo.working_hours.end}
        </div>
      )}
      {totalSlots > 0 && (
        <TimeAxis slots={rooms[0].schedule[0].slots} />
      )}
      {canBook && (
        <div className="tl-hint">
          <i className="fas fa-hand-pointer"></i>
          {t('cal.book_hint', 'Click a free slot or drag across several to reserve the room.')}
        </div>
      )}
      {rooms.map(room => (
        <TimelineRow key={room.id} room={room} canBook={canBook} drag={drag} setDrag={setDrag} />
      ))}
      {booking && (
        <RoomBookingModal
          date={date}
          room={booking.room}
          initialStart={booking.start}
          initialEnd={booking.end}
          onClose={() => setBooking(null)}
          onCreated={() => setReloadKey(k => k + 1)}
        />
      )}
    </div>
  );
}

function TimeAxis({ slots }) {
  const markers = [];
  for (let i = 0; i < slots.length; i++) {
    const time = slots[i].time;
    if (time.endsWith(':00') || time.endsWith(':30')) {
      markers.push({ time, idx: i, isHour: time.endsWith(':00') });
    }
  }
  return (
    <div className="tl-axis">
      {markers.map((m, i) => (
        <div
          key={i}
          className={cls('tl-axis-mark', m.isHour && 'tl-axis-hour')}
          style={{ left: `${(m.idx / slots.length) * 100}%` }}
        >
          {m.isHour ? m.time : ''}
        </div>
      ))}
    </div>
  );
}

function TimelineRow({ room, canBook, drag, setDrag }) {
  const daySchedule = room.schedule && room.schedule[0] ? room.schedule[0] : null;
  const slots = daySchedule ? daySchedule.slots : [];
  const total = slots.length;

  const blocks = useMemo(() => {
    if (!total) return [];
    const out = [];
    let cur = null;
    for (let idx = 0; idx < slots.length; idx++) {
      const slot = slots[idx];
      const occ = slot.status === 'occupied' && slot.info;
      const key = occ ? (slot.info.rental_request_id || slot.info.user_name) : '__free__';
      if (key === '__free__') {
        if (cur) out.push(cur);
        cur = { key, status: slot.status, info: slot.info, time: slot.time, count: 1, idx };
        out.push(cur);
        cur = null;
        continue;
      }
      if (cur && cur.key === key) {
        cur.count++;
        cur.info = slot.info || cur.info;
        continue;
      }
      if (cur) out.push(cur);
      cur = { key, status: slot.status, info: slot.info, time: slot.time, count: 1, idx };
    }
    if (cur) out.push(cur);
    for (const b of out) {
      const [h, m] = b.time.split(':').map(Number);
      const endMin = h * 60 + m + b.count * 30;
      b.endTime = `${String(Math.floor(endMin / 60)).padStart(2, '0')}:${String(endMin % 60).padStart(2, '0')}`;
    }
    return out;
  }, [slots, total]);

  // Extend a drag only over the free slots next to its start.
  const extendTo = (idx) => {
    if (!drag || drag.roomId !== room.id) return;
    const step = idx >= drag.anchor ? 1 : -1;
    let reach = drag.anchor;
    while (reach !== idx && slots[reach + step] && slots[reach + step].status === 'available') {
      reach += step;
    }
    if (reach !== drag.cur) setDrag({ ...drag, cur: reach });
  };
  const inDrag = (idx) => drag && drag.roomId === room.id
    && idx >= Math.min(drag.anchor, drag.cur) && idx <= Math.max(drag.anchor, drag.cur);

  return (
    <div className="tl-row">
      <div className="tl-row-label">
        {room.image_url
          ? <img className="tl-room-photo" src={room.image_url} alt="" loading="lazy"
                 title={t('enlarge_photo', 'Click to enlarge')}
                 style={{cursor: 'zoom-in'}}
                 onClick={() => window.openImageLightbox && window.openImageLightbox(room.image_urls && room.image_urls.length ? room.image_urls : (room.image_full_url || room.image_url))} />
          : <span className="tl-room-photo tl-room-photo-empty"><i className="fas fa-door-open"></i></span>}
        <div className="tl-room-meta">
          <span className="tl-room-name">{room.name}</span>
          {room.capacity > 0 && <span className="tl-room-cap">{room.capacity}<i className="fas fa-users" style={{marginLeft:3,fontSize:9}}></i></span>}
          {room.location && <span className="tl-room-loc">{room.location}</span>}
        </div>
      </div>
      <div className="tl-bar">
        {blocks.map((b, i) => {
          const isBooking = b.status === 'occupied' && b.info;
          const bookable = canBook && b.status === 'available';
          const Segment = isBooking ? 'a' : 'div';
          const title = isBooking
            ? `${b.info.user_name} · ${b.info.project}\n${b.time} — ${b.endTime}${b.info.people_count > 1 ? '\n' + b.info.people_count + ' people' : ''}`
            : b.status === 'past'
              ? t('room.past', 'Past')
              : bookable
                ? `${b.time} — ${b.endTime} · ${t('cal.click_to_book', 'Click to reserve')}`
                : t('available', 'Available');
          return (
            <Segment
              key={i}
              className={cls('tl-seg', b.status, bookable && 'bookable', bookable && inDrag(b.idx) && 'selecting')}
              onMouseDown={bookable ? (e) => {
                if (e.button !== 0) return;
                e.preventDefault();
                setDrag({ roomId: room.id, anchor: b.idx, cur: b.idx });
              } : undefined}
              onMouseEnter={bookable ? () => extendTo(b.idx) : undefined}
              href={isBooking ? b.info.detail_url : undefined}
              style={{
                width: `${(b.count / total) * 100}%`,
                marginRight: b.key === '__free__' ? '2px' : undefined,
              }}
              title={title}
            >
              {isBooking && b.count >= 2 && (
                <span className="tl-seg-text">{b.info.user_name}</span>
              )}
            </Segment>
          );
        })}
      </div>
    </div>
  );
}

const _slotEnd = (time) => {
  const [h, m] = time.split(':').map(Number);
  const end = h * 60 + m + 30;
  return `${String(Math.floor(end / 60)).padStart(2, '0')}:${String(end % 60).padStart(2, '0')}`;
};

/* Reserve a room for one user straight from the day view. Creates the same
   rental as the wizard (rooms only, status "reserved"); the server checks
   working hours and conflicts again. */
function RoomBookingModal({ date, room, initialStart, initialEnd, onClose, onCreated }) {
  const slots = (room.schedule && room.schedule[0] && room.schedule[0].slots) || [];
  const [start, setStart] = useState(initialStart);
  const [end, setEnd] = useState(initialEnd);
  const [user, setUser] = useState(null);
  const [project, setProject] = useState('');
  const [purpose, setPurpose] = useState('');
  const [people, setPeople] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [created, setCreated] = useState(null);
  const pickerInitial = useMemo(() => ({ users: [], urls: ROOM_CAL_CFG.urls }), []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [busy, onClose]);

  // Start: any free slot. End: up to the next taken slot after the start.
  const startOptions = slots.map((s, i) => ({ i, s })).filter(o => o.s.status === 'available');
  const endOptions = [];
  for (let i = start; i < slots.length && slots[i].status === 'available'; i++) {
    endOptions.push({ i: i + 1, label: _slotEnd(slots[i].time) });
  }
  const changeStart = (value) => {
    const s0 = Number(value);
    let maxEnd = s0;
    while (maxEnd < slots.length && slots[maxEnd].status === 'available') maxEnd++;
    const keepLength = Math.max(end - start, 1);
    setStart(s0);
    setEnd(Math.min(s0 + keepLength, maxEnd));
  };

  const startTime = slots[start] ? slots[start].time : '';
  const endTime = slots[end - 1] ? _slotEnd(slots[end - 1].time) : '';

  const submit = async (e) => {
    e.preventDefault();
    if (!user) { setError(t('cal.user_req', 'Please choose a user.')); return; }
    if (!project.trim()) { setError(t('wiz.project_req', 'Please enter a project name.')); return; }
    setBusy(true);
    setError(null);
    // A booking up to midnight ends at 00:00 of the next day.
    let endDate = date;
    let endAt = endTime;
    if (endAt === '24:00') {
      const d = new Date(date + 'T12:00:00');
      d.setDate(d.getDate() + 1);
      endDate = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      endAt = '00:00';
    }
    try {
      const res = await apiPost(ROOM_CAL_CFG.urls.create, {
        user_id: user.id,
        project: project.trim(),
        purpose: purpose.trim(),
        items: [],
        rooms: [{
          id: room.id,
          start_date: date, start_time: startTime,
          end_date: endDate, end_time: endAt,
          people_count: Math.max(1, Number(people) || 1),
        }],
      });
      setCreated(res);
      onCreated();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  const dayLabel = new Date(date + 'T12:00:00').toLocaleDateString('de-DE',
    { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' });

  return (
    <div className="rc-modal-bg" onMouseDown={() => !busy && onClose()}>
      <div className="rc-modal" role="dialog" aria-modal="true" onMouseDown={e => e.stopPropagation()}>
        <div className="rc-modal-head">
          <div>
            <h5>{t('room.reserve', 'Reserve room')}</h5>
            <div className="rc-modal-sub">
              <i className="fas fa-door-open"></i> {room.name}
              <span className="rc-dot">·</span>{dayLabel}
            </div>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}
                  aria-label={t('btn.close', 'Close')}><i className="fas fa-times"></i></button>
        </div>

        {created ? (
          <div className="rc-modal-done">
            <div className="rc-done-line">
              <i className="fas fa-circle-check"></i>
              <div>
                <div className="rc-done-title">{t('cal.created', 'Room reserved')}</div>
                <div className="muted tiny">{room.name} · {startTime} — {endTime} · {user && user.name}</div>
              </div>
            </div>
            <div className="rc-modal-actions">
              <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>{t('btn.close', 'Close')}</button>
              <a className="btn btn-primary btn-sm" href={created.detail_url}>
                <i className="fas fa-arrow-right me-1"></i>{t('cal.open_rental', 'Open rental')}
              </a>
            </div>
          </div>
        ) : (
          <form onSubmit={submit}>
            <div className="rc-grid">
              <label className="rc-field">
                <span>{t('room.start_time', 'Start time')}</span>
                <select className="form-select form-select-sm" value={start} onChange={e => changeStart(e.target.value)}>
                  {startOptions.map(o => <option key={o.i} value={o.i}>{o.s.time}</option>)}
                </select>
              </label>
              <label className="rc-field">
                <span>{t('room.end_time', 'End time')}</span>
                <select className="form-select form-select-sm" value={end} onChange={e => setEnd(Number(e.target.value))}>
                  {endOptions.map(o => <option key={o.i} value={o.i}>{o.label}</option>)}
                </select>
              </label>
              <label className="rc-field">
                <span>{t('cal.people', 'People')}</span>
                <input type="number" min="1" max={room.capacity > 0 ? room.capacity : undefined}
                       className="form-control form-control-sm" value={people}
                       onChange={e => setPeople(e.target.value)} />
              </label>
            </div>

            <div className="rc-field">
              <span>{t('wiz.step1', 'User')} *</span>
              <QuickUserPicker initial={pickerInitial} user={user} setUser={setUser} />
              {ROOM_CAL_CFG.urls.new_user && !user && (
                <a className="rc-link tiny" href={ROOM_CAL_CFG.urls.new_user} target="_blank" rel="noopener">
                  <i className="fas fa-user-plus me-1"></i>{t('wiz.new_user', 'New user')}
                </a>
              )}
            </div>

            <label className="rc-field">
              <span>{t('cal.project', 'Project')} *</span>
              <input type="text" className="form-control form-control-sm" value={project}
                     onChange={e => setProject(e.target.value)} maxLength={255} />
            </label>
            <label className="rc-field">
              <span>{t('cal.purpose', 'Purpose')}</span>
              <textarea className="form-control form-control-sm" rows={2} value={purpose}
                        onChange={e => setPurpose(e.target.value)} />
            </label>

            {error && <div className="rc-error"><i className="fas fa-circle-exclamation me-1"></i>{error}</div>}

            <div className="rc-modal-actions">
              <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>
                {t('btn.cancel', 'Cancel')}
              </button>
              <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !user || !project.trim()}>
                {busy
                  ? <><i className="fas fa-spinner fa-spin me-1"></i>{t('cal.creating', 'Reserving…')}</>
                  : <><i className="fas fa-check me-1"></i>{t('cal.book', 'Reserve')} {startTime}–{endTime}</>}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

/* Reserve dialog for the week and month views: they know only the room and
   the day, so the day's slots are loaded first. window.openRoomBooking(roomId,
   date) opens it; after a reservation the page reloads on close. */
function RoomBookingLauncher() {
  const [req, setReq] = useState(null);      // {roomId, date}
  const [room, setRoom] = useState(null);
  const [error, setError] = useState(null);
  const [created, setCreated] = useState(false);

  useEffect(() => {
    window.openRoomBooking = (roomId, date) => {
      setRoom(null);
      setError(null);
      setReq({ roomId: Number(roomId), date });
    };
    return () => { delete window.openRoomBooking; };
  }, []);

  useEffect(() => {
    if (!req) return;
    let cancelled = false;
    const q = new URLSearchParams({ room_id: req.roomId, start_date: req.date, end_date: req.date });
    apiGet(`${ROOM_CAL_CFG.urls.schedule}?${q}`)
      .then(data => {
        if (cancelled) return;
        const found = (data.rooms || []).find(r => r.id === req.roomId);
        if (!found) throw new Error(t('no_rooms', 'Room not found'));
        setRoom(found);
      })
      .catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [req]);

  if (!req) return null;

  const close = () => {
    setReq(null);
    if (created) window.location.reload();
  };
  const slots = (room && room.schedule && room.schedule[0] && room.schedule[0].slots) || [];
  const first = slots.findIndex(s => s.status === 'available');

  if (room && first >= 0) {
    // Suggest one hour from the first free slot, within the free run.
    let end = first + 1;
    while (end < first + 2 && end < slots.length && slots[end].status === 'available') end++;
    return (
      <RoomBookingModal
        date={req.date}
        room={room}
        initialStart={first}
        initialEnd={end}
        onClose={close}
        onCreated={() => setCreated(true)}
      />
    );
  }

  const dayUrl = `${ROOM_CAL_CFG.urls.day_view}?date=${req.date}`;
  return (
    <div className="rc-modal-bg" onMouseDown={close}>
      <div className="rc-modal rc-modal-small" role="dialog" aria-modal="true" onMouseDown={e => e.stopPropagation()}>
        <div className="rc-modal-head">
          <h5>{t('room.reserve', 'Reserve room')}</h5>
          <button type="button" className="btn btn-ghost btn-sm" onClick={close}
                  aria-label={t('btn.close', 'Close')}><i className="fas fa-times"></i></button>
        </div>
        {error ? (
          <div className="rc-error"><i className="fas fa-circle-exclamation me-1"></i>{error}</div>
        ) : !room ? (
          <div className="rc-modal-wait"><i className="fas fa-spinner fa-spin me-2"></i>{t('loading', 'Loading...')}</div>
        ) : (
          <div className="rc-modal-wait">
            <i className="fas fa-ban me-2"></i>{room.name}: {t('cal.no_free', 'No free time left on this day.')}
          </div>
        )}
        <div className="rc-modal-actions">
          <a className="btn btn-ghost btn-sm" href={dayUrl}>
            <i className="fas fa-calendar-day me-1"></i>{t('cal.open_day', 'Open day view')}
          </a>
          <button type="button" className="btn btn-primary btn-sm" onClick={close}>{t('btn.close', 'Close')}</button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { RoomCalendar, RoomBookingLauncher });
