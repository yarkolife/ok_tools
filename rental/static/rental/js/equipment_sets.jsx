/* =========================================================
   rental/static/rental/js/equipment_sets.jsx
   React island for equipment sets management.
   Depends on: shared.jsx (cls, apiPost, apiGet, getCookie, t)
   ========================================================= */

function EquipmentSetsScreen({ initial }) {
  const { urls } = initial;

  const [sets, setSets] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [showForm, setShowForm] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);

  const loadSets = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiGet(urls.api_get_all_equipment_sets);
      setSets(data.sets || []);
    } catch (err) {
      setError(err.message || t('sets.load_error', 'Could not load equipment sets.'));
      setSets([]);
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    loadSets();
  }, []);

  const handleDelete = async (setId, setName) => {
    if (!confirm(t('sets.confirm_delete', 'Delete set "{name}"?').replace('{name}', setName))) return;
    try {
      const url = urls.api_delete_equipment_set.replace('/0/', `/${setId}/`);
      const response = await fetch(url, {
        method: 'DELETE',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': getCookie('csrftoken'),
        },
      });
      if (!response.ok) {
        let message = `${url} → ${response.status}`;
        try {
          const body = await response.clone().json();
          if (body && body.error) message = body.error;
        } catch {}
        throw new Error(message);
      }
      await loadSets();
    } catch (err) {
      alert(t('sets.delete_error', 'Could not delete set: ') + err.message);
    }
  };

  return (
    <>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div className="muted tiny">
          {loading ? t('loading', 'Loading…') : `${sets.length} ${t('sets.total', 'sets')}`}
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setShowForm(s => !s)}>
          <i className={`fas ${showForm ? 'fa-chevron-up' : 'fa-plus'} me-1`}></i>
          {showForm ? t('sets.hide_form', 'Hide form') : t('sets.new_set', 'New set')}
        </button>
      </div>

      {error && (
        <div className="alert alert-danger" style={{fontSize: 13}}>
          <i className="fas fa-triangle-exclamation me-2"></i>{error}
        </div>
      )}

      {showForm && (
        <CreateSetForm
          urls={urls}
          onCreated={() => {
            setShowForm(false);
            loadSets();
          }}
          onCancel={() => setShowForm(false)}
          submitting={submitting}
          setSubmitting={setSubmitting}
        />
      )}

      {loading ? (
        <div className="p-5 text-center muted">
          <i className="fas fa-spinner fa-spin" style={{fontSize: 24}}></i>
          <div className="mt-2">{t('loading', 'Loading…')}</div>
        </div>
      ) : sets.length === 0 ? (
        <div className="surface p-5 text-center muted">
          <i className="fas fa-layer-group" style={{fontSize: 32, opacity: 0.3}}></i>
          <div className="mt-2">{t('sets.empty', 'No equipment sets yet.')}</div>
          <div className="tiny mt-1">{t('sets.empty_sub', 'Create your first set using the button above.')}</div>
        </div>
      ) : (
        <div className="row g-3">
          {sets.map(s => (
            <div key={s.id} className="col-md-6 col-lg-4">
              <div className="surface" style={{padding: 16, borderRadius: 12, height: '100%', display: 'flex', flexDirection: 'column'}}>
                <div className="d-flex align-items-start justify-content-between mb-2">
                  <div style={{minWidth: 0, flex: 1}}>
                    <div className="set-title">{s.name}</div>
                    {s.description && (
                      <div className="muted tiny mt-1">{s.description}</div>
                    )}
                  </div>
                  <button
                    className="btn btn-ghost btn-sm ms-2"
                    style={{padding: '2px 8px', fontSize: 12}}
                    onClick={() => handleDelete(s.id, s.name)}
                    title={t('sets.delete', 'Löschen')}
                  >
                    <i className="fas fa-trash" style={{color: 'var(--accent-red)'}}></i>
                  </button>
                </div>

                <div className="mt-auto pt-2" style={{borderTop: '1px solid var(--line)'}}>
                  <div className="muted tiny mb-1">
                    {s.items_count} {t('sets.items', 'Artikel')} · {s.created_at}
                  </div>
                  {s.items && s.items.length > 0 && (
                    <div style={{display: 'flex', flexWrap: 'wrap', gap: 4}}>
                      {s.items.map(item => (
                        <span key={item.id} className="tag">
                          {item.inventory_item.description || item.inventory_item.inventory_number} × {item.quantity}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function CreateSetForm({ urls, onCreated, onCancel, submitting, setSubmitting }) {
  const [name, setName] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [search, setSearch] = React.useState('');
  const [searchResults, setSearchResults] = React.useState([]);
  const [searchLoading, setSearchLoading] = React.useState(false);
  const [selectedItems, setSelectedItems] = React.useState([]);
  const [formError, setFormError] = React.useState('');

  React.useEffect(() => {
    if (!search.trim()) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ q: search.trim() });
      apiGet(`${urls.api_inventory_search}?${params}`)
        .then(data => setSearchResults(data.items || []))
        .catch(() => setSearchResults([]))
        .finally(() => setSearchLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [search, urls.api_inventory_search]);

  const addItem = (item) => {
    if (selectedItems.some(si => si.inventory_item_id === item.id)) return;
    setSelectedItems(prev => [...prev, {
      inventory_item_id: item.id,
      name: item.name,
      num: item.num,
      quantity: 1,
    }]);
    setSearch('');
    setSearchResults([]);
  };

  const removeItem = (id) => {
    setSelectedItems(prev => prev.filter(si => si.inventory_item_id !== id));
  };

  const setQty = (id, qty) => {
    const q = Math.max(1, parseInt(qty, 10) || 1);
    setSelectedItems(prev => prev.map(si => si.inventory_item_id === id ? { ...si, quantity: q } : si));
  };

  const submit = async () => {
    if (!name.trim()) {
      setFormError(t('sets.need_name', 'Please enter a set name.'));
      return;
    }
    if (selectedItems.length === 0) {
      setFormError(t('sets.need_items', 'Please add at least one item.'));
      return;
    }
    setFormError('');
    setSubmitting(true);
    try {
      await apiPost(urls.api_create_equipment_set, {
        name: name.trim(),
        description: description.trim(),
        is_active: true,
        items: selectedItems.map(si => ({
          inventory_item_id: si.inventory_item_id,
          quantity: si.quantity,
        })),
      });
      onCreated();
    } catch (err) {
      setFormError(err.message || t('sets.create_error', 'Could not create set.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="surface mb-3" style={{padding: 20, borderRadius: 12}}>
      <div className="section-head mb-3">
        <i className="fas fa-layer-group me-2" style={{color: 'var(--brand)'}}></i>
        <span>{t('sets.create_title', 'Gerätesatz erstellen')}</span>
      </div>

      {formError && (
        <div className="alert alert-danger mb-3" style={{fontSize: 13}}>
          <i className="fas fa-triangle-exclamation me-2"></i>{formError}
        </div>
      )}

      <div className="row g-3 mb-3">
        <div className="col-md-6">
          <label className="form-label">{t('sets.name', 'Name')}</label>
          <input
            type="text"
            className="form-control"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder={t('sets.name_ph', 'z.B. Podcast-Kit')}
          />
        </div>
        <div className="col-md-6">
          <label className="form-label">{t('sets.description', 'Beschreibung')}</label>
          <input
            type="text"
            className="form-control"
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder={t('sets.desc_ph', 'Optionale Beschreibung…')}
          />
        </div>
      </div>

      <div className="mb-4">
        <label className="form-label d-block">{t('sets.search_items', 'Inventarartikel suchen')}</label>
        <div className="search" style={{display: 'block', width: '100%', maxWidth: 760}}>
          <i className="fas fa-search"></i>
          <input
            type="text"
            className="form-control"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={t('sets.search_ph', 'Suche nach Name, Nummer oder Hersteller…')}
          />
        </div>

        {searchLoading && (
          <div className="muted tiny mt-2">
            <i className="fas fa-spinner fa-spin me-1"></i>{t('loading', 'Suchen…')}
          </div>
        )}

        {searchResults.length > 0 && (
          <div className="mt-2" style={{border: '1px solid var(--line)', borderRadius: 8, maxHeight: 220, overflow: 'auto', background: '#fff'}}>
            {searchResults.map(item => (
              <div
                key={item.id}
                className="d-flex align-items-center justify-content-between"
                style={{padding: '8px 12px', borderBottom: '1px solid var(--line)', cursor: 'pointer'}}
                onClick={() => addItem(item)}
              >
                <div style={{minWidth: 0, flex: 1}}>
                  <div style={{fontSize: 13, fontWeight: 500}}>{item.name}</div>
                  <div className="muted tiny">{item.num} · {item.cat}</div>
                </div>
                <button className="btn btn-ghost btn-sm" style={{fontSize: 12, padding: '2px 8px'}}>
                  <i className="fas fa-plus me-1"></i>{t('sets.add', 'Hinzufügen')}
                </button>
              </div>
            ))}
          </div>
        )}

        {search.trim() && !searchLoading && searchResults.length === 0 && (
          <div className="muted tiny mt-2">{t('sets.no_results', 'Keine Artikel gefunden.')}</div>
        )}
      </div>

      {selectedItems.length > 0 && (
        <div className="mb-4">
          <label className="form-label">{t('sets.selected_items', 'Ausgewählte Artikel')}</label>
          <div style={{border: '1px solid var(--line)', borderRadius: 8, background: '#fff'}}>
            {selectedItems.map((si, idx) => (
              <div
                key={si.inventory_item_id}
                className="d-flex align-items-center justify-content-between"
                style={{padding: '8px 12px', borderBottom: idx < selectedItems.length - 1 ? '1px solid var(--line)' : 'none'}}
              >
                <div style={{minWidth: 0, flex: 1}}>
                  <div style={{fontSize: 13, fontWeight: 500}}>{si.name}</div>
                  <div className="muted tiny">{si.num}</div>
                </div>
                <div className="d-flex align-items-center gap-2">
                  <input
                    type="number"
                    className="form-control form-control-sm"
                    style={{width: 60, textAlign: 'center'}}
                    min={1}
                    value={si.quantity}
                    onChange={e => setQty(si.inventory_item_id, e.target.value)}
                  />
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{fontSize: 12, padding: '2px 8px', color: 'var(--accent-red)'}}
                    onClick={() => removeItem(si.inventory_item_id)}
                  >
                    <i className="fas fa-times"></i>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="d-flex align-items-center gap-2 mt-3">
        <button className="btn btn-primary btn-sm" onClick={submit} disabled={submitting}>
          {submitting ? (
            <><i className="fas fa-spinner fa-spin me-1"></i>{t('sets.creating', 'Wird erstellt…')}</>
          ) : (
            <><i className="fas fa-check me-1"></i>{t('sets.create', 'Set erstellen')}</>
          )}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onCancel} disabled={submitting}>
          {t('sets.cancel', 'Abbrechen')}
        </button>
      </div>
    </div>
  );
}

Object.assign(window, { EquipmentSetsScreen });
