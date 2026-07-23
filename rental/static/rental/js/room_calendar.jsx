const { useState, useEffect, useMemo } = React;

function RoomCalendar({ date }) {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dayInfo, setDayInfo] = useState(null);

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
  }, [date]);

  if (loading) {
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
      {rooms.map(room => (
        <TimelineRow key={room.id} room={room} />
      ))}
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

function TimelineRow({ room }) {
  const daySchedule = room.schedule && room.schedule[0] ? room.schedule[0] : null;
  const slots = daySchedule ? daySchedule.slots : [];
  const total = slots.length;

  const blocks = useMemo(() => {
    if (!total) return [];
    const out = [];
    let cur = null;
    for (const slot of slots) {
      const occ = slot.status === 'occupied' && slot.info;
      const key = occ ? (slot.info.rental_request_id || slot.info.user_name) : '__free__';
      if (key === '__free__') {
        if (cur) out.push(cur);
        cur = { key, status: slot.status, info: slot.info, time: slot.time, count: 1 };
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
      cur = { key, status: slot.status, info: slot.info, time: slot.time, count: 1 };
    }
    if (cur) out.push(cur);
    for (const b of out) {
      const [h, m] = b.time.split(':').map(Number);
      const endMin = h * 60 + m + b.count * 30;
      b.endTime = `${String(Math.floor(endMin / 60)).padStart(2, '0')}:${String(endMin % 60).padStart(2, '0')}`;
    }
    return out;
  }, [slots, total]);

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
        {blocks.map((b, i) => (
          <div
            key={i}
            className={cls('tl-seg', b.status)}
            style={{
              width: `${(b.count / total) * 100}%`,
              marginRight: b.key === '__free__' ? '2px' : undefined,
            }}
            title={b.status === 'occupied' && b.info
              ? `${b.info.user_name} · ${b.info.project}\n${b.time} — ${b.endTime}${b.info.people_count > 1 ? '\n' + b.info.people_count + ' people' : ''}`
              : t('available', 'Available')
            }
          >
            {b.status === 'occupied' && b.info && b.count >= 2 && (
              <span className="tl-seg-text">{b.info.user_name}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { RoomCalendar });