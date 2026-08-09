(() => {
  const dataNode = document.getElementById('notifications-data');
  const initial = dataNode ? JSON.parse(dataNode.textContent) : null;
  if (!initial) return;

  const { useMemo, useState } = React;

  const categoryMeta = {
    action_required: { icon: 'fa-triangle-exclamation', tone: 'amber' },
    info: { icon: 'fa-circle-info', tone: 'green' },
    problem: { icon: 'fa-circle-exclamation', tone: 'red' },
  };

  const moduleMeta = {
    rental: { icon: 'fa-toolbox', tone: 'blue' },
    licenses: { icon: 'fa-file-signature', tone: 'violet' },
    media_files: { icon: 'fa-photo-film', tone: 'green' },
    austausch: { icon: 'fa-arrows-rotate', tone: 'teal' },
    planung: { icon: 'fa-calendar-days', tone: 'violet' },
    registration: { icon: 'fa-user-check', tone: 'blue' },
    tools: { icon: 'fa-screwdriver-wrench', tone: 'amber' },
    system: { icon: 'fa-server', tone: 'slate' },
  };

  function viewUrl(view) {
    const params = new URLSearchParams(window.location.search);
    params.set('view', view);
    params.delete('page');
    return `${initial.urls.feed}?${params.toString()}`;
  }

  function pageUrl(page) {
    const params = new URLSearchParams(window.location.search);
    params.set('page', page);
    return `${initial.urls.feed}?${params.toString()}`;
  }

  function StatCard({ icon, tone, label, value, note, active, onClick }) {
    return (
      <button type="button" className={`overview-card ${active ? 'active' : ''}`}
              aria-pressed={active} onClick={onClick}>
        <span className={`overview-icon tone-${tone}`}>
          <i className={`fas ${icon}`} aria-hidden="true"></i>
        </span>
        <span className="overview-copy">
          <span className="overview-label">{label}</span>
          <strong>{value}</strong>
          {note ? <span className="overview-note">{note}</span> : null}
        </span>
      </button>
    );
  }

  function Sidebar() {
    return (
      <aside className="notifications-sidebar">
        <div className="sidebar-section">
          <div className="sidebar-title">{initial.i18n.notification}</div>
          <a className="sidebar-link active" href={initial.urls.feed}>
            <i className="fas fa-bell" aria-hidden="true"></i>
            <span>{initial.i18n.title}</span>
            <span className="sidebar-count bad">{initial.stats.open}</span>
          </a>
          <a className="sidebar-link" href={viewUrl('snoozed')}>
            <i className="fas fa-clock" aria-hidden="true"></i>
            <span>{initial.i18n.postponed}</span>
            <span className="sidebar-count warn">{initial.stats.snoozed}</span>
          </a>
          <a className="sidebar-link" href={viewUrl('handled')}>
            <i className="fas fa-circle-check" aria-hidden="true"></i>
            <span>{initial.i18n.handled}</span>
            <span className="sidebar-count">{initial.stats.handled}</span>
          </a>
          <a className="sidebar-link" href={viewUrl('all')}>
            <i className="fas fa-clock-rotate-left" aria-hidden="true"></i>
            <span>{initial.i18n.chronicle}</span>
          </a>
        </div>
        <div className="sidebar-section">
          <div className="sidebar-title">{initial.i18n.settings}</div>
          <a className="sidebar-link" href={initial.urls.subscriptions}>
            <i className="fas fa-sliders" aria-hidden="true"></i>
            <span>{initial.i18n.subscriptions}</span>
          </a>
          {initial.urls.settings ? (
            <a className="sidebar-link" href={initial.urls.settings}>
              <i className="fas fa-gear" aria-hidden="true"></i>
              <span>{initial.i18n.settings}</span>
            </a>
          ) : null}
          {initial.urls.stats ? (
            <a className="sidebar-link" href={initial.urls.stats}>
              <i className="fas fa-chart-column" aria-hidden="true"></i>
              <span>{initial.i18n.statistics}</span>
            </a>
          ) : null}
        </div>
        <div className="sidebar-user">
          <span className="user-avatar">{initial.user.initials || '?'}</span>
          <span>
            <strong>{initial.user.name}</strong>
            <small>{initial.user.email}</small>
          </span>
        </div>
      </aside>
    );
  }

  function Filters({ search, setSearch }) {
    const [expanded, setExpanded] = useState(Boolean(
      initial.filters.type || initial.filters.older ||
      initial.filters.dateFrom || initial.filters.dateTo
    ));
    return (
      <div className="filter-block">
        <div className="filter-row">
          <label className="search-box">
            <i className="fas fa-magnifying-glass" aria-hidden="true"></i>
            <span className="visually-hidden">{initial.i18n.search}</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)}
                   placeholder={initial.i18n.search} />
          </label>
          <button type="button" className={`filter-toggle ${expanded ? 'active' : ''}`}
                  onClick={() => setExpanded(!expanded)}>
            <i className="fas fa-filter" aria-hidden="true"></i>
            {initial.i18n.filters}
            <i className={`fas fa-chevron-${expanded ? 'up' : 'down'}`} aria-hidden="true"></i>
          </button>
          <div className="view-tabs" role="navigation" aria-label={initial.i18n.state}>
            {[
              ['all', initial.i18n.all],
              ['open', initial.i18n.open],
              ['snoozed', initial.i18n.postponed],
              ['handled', initial.i18n.handled],
            ].map(([value, label]) => (
              <a key={value} className={initial.view === value ? 'active' : ''}
                 href={viewUrl(value)}>{label}</a>
            ))}
          </div>
        </div>
        {expanded ? (
          <form className="advanced-filters" action={initial.urls.feed} method="get">
            <input type="hidden" name="view" value={initial.view} />
            <label>
              <span>{initial.i18n.module}</span>
              <select name="module" defaultValue={initial.filters.module}>
                <option value="">{initial.i18n.all}</option>
                {initial.filterOptions.modules.map((option) => (
                  <option value={option.value} key={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              <span>{initial.i18n.eventType}</span>
              <select name="type" defaultValue={initial.filters.type}>
                <option value="">{initial.i18n.all}</option>
                {initial.filterOptions.types.map((option) => (
                  <option value={option.value} key={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              <span>{initial.i18n.category}</span>
              <select name="category" defaultValue={initial.filters.category}>
                <option value="">{initial.i18n.all}</option>
                {initial.filterOptions.categories.map((option) => (
                  <option value={option.value} key={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label className="compact-filter">
              <span>{initial.i18n.olderThan}</span>
              <input type="number" name="older" min="0" step="1"
                     defaultValue={initial.filters.older} />
            </label>
            <label>
              <span>{initial.i18n.from}</span>
              <input type="date" name="date_from" defaultValue={initial.filters.dateFrom} />
            </label>
            <label>
              <span>{initial.i18n.to}</span>
              <input type="date" name="date_to" defaultValue={initial.filters.dateTo} />
            </label>
            <button className="button primary" type="submit">{initial.i18n.applyFilters}</button>
            <a className="button ghost" href={`${initial.urls.feed}?view=${initial.view}`}>
              {initial.i18n.reset}
            </a>
          </form>
        ) : null}
      </div>
    );
  }

  function BulkActions({ selected, allMatches, setAllMatches, allVisible,
                         toggleAll, view, overviewMode, overviewLabel,
                         clearOverview }) {
    if (overviewMode === 'expected') {
      return (
        <div className="bulk-actions overview-active">
          <span><i className="fas fa-filter" aria-hidden="true"></i>
            {initial.i18n.showingOverview} <strong>{overviewLabel}</strong>
          </span>
          <button type="button" className="button ghost" onClick={clearOverview}>
            <i className="fas fa-xmark" aria-hidden="true"></i>{initial.i18n.backToView}
          </button>
        </div>
      );
    }
    const canSubmit = selected.length > 0 || allMatches;
    let primaryActions;
    if (view === 'handled') {
      primaryActions = [['reopen', 'fa-arrow-rotate-left', initial.i18n.reopen]];
    } else if (view === 'snoozed') {
      primaryActions = [
        ['wake', 'fa-clock-rotate-left', initial.i18n.showAgain],
        ['done', 'fa-check', initial.i18n.markHandled],
      ];
    } else {
      primaryActions = [
        ['done', 'fa-check', initial.i18n.markHandled],
        ['snooze', 'fa-clock', initial.i18n.postpone],
      ];
    }
    return (
      <div className="bulk-actions">
        {overviewMode ? (
          <span className="overview-mode-label">
            <i className="fas fa-filter" aria-hidden="true"></i>
            {initial.i18n.showingOverview} <strong>{overviewLabel}</strong>
            <button type="button" onClick={clearOverview} aria-label={initial.i18n.backToView}>
              <i className="fas fa-xmark" aria-hidden="true"></i>
            </button>
          </span>
        ) : null}
        <label className="check-label">
          <input type="checkbox" checked={allVisible} onChange={toggleAll} />
          <span>{initial.i18n.selectAllPage}</span>
        </label>
        {!overviewMode ? <label className="check-label all-matches">
          <input type="checkbox" checked={allMatches}
                 onChange={(event) => setAllMatches(event.target.checked)} />
          <span>{initial.i18n.applyAll} ({initial.shownCount})</span>
        </label> : null}
        <span className="bulk-spacer"></span>
        {primaryActions.map(([action, icon, label]) => (
          <button className="button ghost" type="submit" name="action" value={action}
                  disabled={!canSubmit} key={action}>
            <i className={`fas ${icon}`} aria-hidden="true"></i>{label}
          </button>
        ))}
        <button className="button ghost danger" type="submit" name="action" value="suppress"
                disabled={!canSubmit}
                onClick={(event) => {
                  if (!window.confirm(initial.i18n.suppressConfirm)) event.preventDefault();
                }}>
          <i className="fas fa-bell-slash" aria-hidden="true"></i>{initial.i18n.suppress}
        </button>
      </div>
    );
  }

  function EventRow({ row, checked, toggle, active, select }) {
    const category = categoryMeta[row.category] || categoryMeta.info;
    const module = moduleMeta[row.module] || { icon: 'fa-box', tone: 'slate' };
    return (
      <div className={`event-row ${active ? 'active' : ''}`} onClick={() => select(row)}>
        {row.selectable === false ? <span className="row-check"></span> : (
          <label className="row-check" onClick={(event) => event.stopPropagation()}>
            <input type="checkbox" checked={checked} onChange={() => toggle(row.id)} />
          </label>
        )}
        <div className="status-cell">
          <span className={`status-dot tone-${category.tone}`}></span>
          <span>{row.categoryLabel}</span>
        </div>
        <div><span className={`module-chip tone-${module.tone}`}>
          <i className={`fas ${module.icon}`} aria-hidden="true"></i>{row.moduleLabel}
        </span></div>
        <div className="type-cell">
          <strong>{row.label}</strong>
          <small>{row.description}</small>
        </div>
        <div className="subject-cell">
          <strong>{row.message}</strong>
          <small>{row.objectId ? `#${row.objectId}` : row.eventType}</small>
        </div>
        <time dateTime={row.occurredAt}>{row.occurredAtLabel}</time>
        <div>
          <span className={`state-chip state-${row.status || 'info'}`}>{row.statusLabel}</span>
          {row.snoozedUntil ? <small className="snooze-time">{row.snoozedUntil}</small> : null}
        </div>
        <div className="row-actions" onClick={(event) => event.stopPropagation()}>
          {row.url ? (
            <a href={row.url} title={initial.i18n.viewItem} aria-label={initial.i18n.viewItem}>
              <i className="fas fa-arrow-up-right-from-square" aria-hidden="true"></i>
            </a>
          ) : null}
          <button type="button" onClick={() => select(row)} title={initial.i18n.details}
                  aria-label={initial.i18n.details}>
            <i className="fas fa-eye" aria-hidden="true"></i>
          </button>
        </div>
      </div>
    );
  }

  function EmptyState() {
    return (
      <div className="empty-state">
        <span className="empty-icon"><i className="fas fa-inbox" aria-hidden="true"></i></span>
        <strong>{initial.i18n.noRows}</strong>
      </div>
    );
  }

  function Pagination({ enabled }) {
    const page = initial.pagination;
    if (!enabled || page.pages <= 1) return null;
    return (
      <div className="pagination-row">
        {page.hasPrevious ? <a href={pageUrl(page.previous)}><i className="fas fa-chevron-left"></i> {initial.i18n.previous}</a> : <span />}
        <span>{initial.i18n.page} {page.number} {initial.i18n.of} {page.pages}</span>
        {page.hasNext ? <a href={pageUrl(page.next)}>{initial.i18n.next} <i className="fas fa-chevron-right"></i></a> : <span />}
      </div>
    );
  }

  function Expectations() {
    return (
      <aside className="expectations-panel">
        <div className="panel-heading">
          <span>{initial.i18n.todayExpectations}</span>
          <span className="info-badge"><i className="fas fa-circle-info"></i></span>
        </div>
        {initial.expectations.length ? initial.expectations.map((group) => {
          const module = moduleMeta[group.module] || { icon: 'fa-calendar', tone: 'blue' };
          return (
            <div className="expectation-card" key={group.code}>
              <span className={`expectation-icon tone-${module.tone}`}>
                <i className={`fas ${module.icon}`} aria-hidden="true"></i>
              </span>
              <div className="expectation-copy">
                <strong>{group.label}</strong>
                <span className="expectation-count">{group.count}</span>
                <small>{group.moduleLabel}</small>
                <p>{group.description}</p>
                {group.items.slice(0, 3).map((item, index) => (
                  item.url ? <a href={item.url} key={index}>{item.message}</a>
                           : <span className="expectation-item" key={index}>{item.message}</span>
                ))}
              </div>
            </div>
          );
        }) : (
          <div className="expectations-empty">
            <i className="fas fa-calendar-check" aria-hidden="true"></i>
            <span>{initial.i18n.noExpectations}</span>
          </div>
        )}
      </aside>
    );
  }

  function DetailDrawer({ row, close }) {
    if (!row) return null;
    const category = categoryMeta[row.category] || categoryMeta.info;
    return (
      <section className="detail-drawer" aria-label={initial.i18n.details}>
        <div className="drawer-grip"></div>
        <button type="button" className="drawer-close" onClick={close} aria-label={initial.i18n.close}>
          <i className="fas fa-xmark" aria-hidden="true"></i>
        </button>
        <div className="drawer-subject">
          <h2>{row.message}</h2>
          <span className="drawer-category">
            <span className={`status-dot tone-${category.tone}`}></span>{row.categoryLabel}
          </span>
          <small>{row.moduleLabel} · {row.objectId ? `#${row.objectId}` : row.eventType}</small>
        </div>
        <div className="drawer-meta">
          <span><b>{initial.i18n.eventType}</b>{row.label}</span>
          <span><b>{initial.i18n.time}</b>{row.occurredAtLabel}</span>
          <span><b>{initial.i18n.state}</b>{row.statusLabel}</span>
        </div>
        <div className="drawer-description">
          <b>{initial.i18n.description}</b>
          <p>{row.description}</p>
          {row.details.length ? (
            <dl>{row.details.map((detail) => (
              <React.Fragment key={detail.key}>
                <dt>{detail.label}</dt><dd>{detail.value}</dd>
              </React.Fragment>
            ))}</dl>
          ) : null}
        </div>
        <div className="drawer-actions">
          {row.url ? <a className="button primary" href={row.url}>
            {initial.i18n.viewItem}<i className="fas fa-arrow-right" aria-hidden="true"></i>
          </a> : null}
        </div>
      </section>
    );
  }

  function App() {
    const [search, setSearch] = useState('');
    const [selected, setSelected] = useState([]);
    const [allMatches, setAllMatches] = useState(false);
    const [activeRow, setActiveRow] = useState(initial.rows[0] || null);
    const [overviewMode, setOverviewMode] = useState(null);
    const overviewLabels = {
      expected: initial.i18n.expectedToday,
      new: initial.i18n.newSinceVisit,
      action: initial.i18n.actionRequired,
      snoozed: initial.i18n.postponed,
      problems: initial.i18n.problems,
    };
    const overviewRows = initial.overviewRows || {
      expected: [], new: [], action: [], snoozed: [], problems: [],
    };
    const sourceRows = overviewMode ? overviewRows[overviewMode] : initial.rows;
    const visibleRows = useMemo(() => {
      const query = search.trim().toLocaleLowerCase();
      if (!query) return sourceRows;
      return sourceRows.filter((row) => [
        row.label, row.message, row.description, row.moduleLabel,
        row.categoryLabel, ...row.details.map((detail) => detail.value),
      ].join(' ').toLocaleLowerCase().includes(query));
    }, [search, overviewMode]);
    const visibleIds = visibleRows
      .filter((row) => row.selectable !== false).map((row) => row.id);
    const allVisible = visibleIds.length > 0 && visibleIds.every((id) => selected.includes(id));
    const toggle = (id) => setSelected((current) => (
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id]
    ));
    const toggleAll = () => setSelected((current) => (
      allVisible ? current.filter((id) => !visibleIds.includes(id))
                 : Array.from(new Set([...current, ...visibleIds]))
    ));
    const selectOverview = (mode) => {
      const rows = overviewRows[mode] || [];
      setOverviewMode(mode);
      setSearch('');
      setSelected([]);
      setAllMatches(false);
      setActiveRow(rows[0] || null);
      window.requestAnimationFrame(() => {
        document.querySelector('.content-grid')?.scrollIntoView({
          behavior: 'smooth', block: 'start',
        });
      });
    };
    const clearOverview = () => {
      setOverviewMode(null);
      setSelected([]);
      setAllMatches(false);
      setActiveRow(initial.rows[0] || null);
    };
    const effectiveView = overviewMode === 'snoozed' ? 'snoozed'
      : overviewMode === 'action' ? 'open'
      : overviewMode ? 'all' : initial.view;

    return (
      <div className={activeRow ? 'notifications-app drawer-open' : 'notifications-app'}>
        <header className="topbar">
          <a className="brand" href={initial.urls.admin}>
            <i className="fas fa-toolbox" aria-hidden="true"></i>
            <span>OK Tools <b>— {initial.i18n.title}</b></span>
          </a>
          <a className="admin-link" href={initial.urls.admin}>
            <i className="fas fa-gear" aria-hidden="true"></i>{initial.i18n.administration}
          </a>
        </header>
        <div className="app-frame">
          <Sidebar />
          <main className="notifications-main">
            <div className="page-heading">
              <div>
                <h1>{initial.i18n.title}</h1>
                <p>{initial.i18n.subtitle}</p>
              </div>
              <a className="button ghost" href={initial.urls.subscriptions}>
                <i className="fas fa-sliders" aria-hidden="true"></i>{initial.i18n.subscriptions}
              </a>
            </div>

            {!initial.hasSubscriptions ? (
              <div className="subscription-notice">
                <i className="fas fa-circle-info" aria-hidden="true"></i>
                <span>{initial.i18n.noSubscriptions}</span>
                <a href={initial.urls.subscriptions}>{initial.i18n.chooseModules}</a>
              </div>
            ) : null}

            <section aria-labelledby="today-overview">
              <h2 className="section-label" id="today-overview">{initial.i18n.todayOverview}</h2>
              <div className="overview-grid">
                <StatCard icon="fa-calendar-day" tone="blue" label={initial.i18n.expectedToday} value={initial.stats.expected}
                          active={overviewMode === 'expected'} onClick={() => selectOverview('expected')} />
                <StatCard icon="fa-wand-magic-sparkles" tone="green" label={initial.i18n.newSinceVisit} value={initial.stats.new}
                          active={overviewMode === 'new'} onClick={() => selectOverview('new')} />
                <StatCard icon="fa-triangle-exclamation" tone="amber" label={initial.i18n.actionRequired} value={initial.stats.open}
                          active={overviewMode === 'action'} onClick={() => selectOverview('action')} />
                <StatCard icon="fa-clock" tone="violet" label={initial.i18n.postponed} value={initial.stats.snoozed}
                          active={overviewMode === 'snoozed'} onClick={() => selectOverview('snoozed')} />
                <StatCard icon="fa-circle-exclamation" tone="red" label={initial.i18n.problems} value={initial.stats.problems}
                          active={overviewMode === 'problems'} onClick={() => selectOverview('problems')} />
              </div>
            </section>

            <Filters search={search} setSearch={setSearch} />
            <div className="content-grid">
              <form className="events-surface" method="post">
                <input type="hidden" name="csrfmiddlewaretoken" value={initial.csrfToken} />
                <input type="hidden" name="filter_query" value={overviewMode ? '' : initial.filterQuery} />
                <input type="hidden" name="view" value={effectiveView} />
                {allMatches ? <input type="hidden" name="select_all" value="1" /> : null}
                {selected.map((id) => <input type="hidden" name="event_ids" value={id} key={id} />)}
                <BulkActions selected={selected} allMatches={allMatches}
                             setAllMatches={setAllMatches} allVisible={allVisible}
                             toggleAll={toggleAll} view={effectiveView}
                             overviewMode={overviewMode}
                             overviewLabel={overviewLabels[overviewMode]}
                             clearOverview={clearOverview} />
                <div className="table-heading">
                  <span></span><span>{initial.i18n.status}</span><span>{initial.i18n.module}</span>
                  <span>{initial.i18n.eventType}</span><span>{initial.i18n.subject}</span>
                  <span>{initial.i18n.time}</span><span>{initial.i18n.state}</span><span>{initial.i18n.actions}</span>
                </div>
                <div className="event-list">
                  {visibleRows.length ? visibleRows.map((row) => (
                    <EventRow row={row} checked={selected.includes(row.id)} toggle={toggle}
                              active={activeRow && activeRow.id === row.id}
                              select={setActiveRow} key={row.id} />
                  )) : <EmptyState />}
                </div>
                <div className="list-footer">
                  <span>{visibleRows.length} {initial.i18n.results}</span>
                  <Pagination enabled={!overviewMode} />
                </div>
              </form>
              <Expectations />
            </div>
          </main>
        </div>
        <DetailDrawer row={activeRow} close={() => setActiveRow(null)} />
      </div>
    );
  }

  ReactDOM.createRoot(document.getElementById('notifications-root')).render(<App />);
})();
