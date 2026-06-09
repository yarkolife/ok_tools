(() => {
  const rental = JSON.parse(document.getElementById('rental-data').textContent);
  const items = JSON.parse(document.getElementById('rental-items').textContent);
  const rooms = JSON.parse(document.getElementById('rental-rooms').textContent);
  const issues = JSON.parse(document.getElementById('rental-issues').textContent);
  const history = JSON.parse(document.getElementById('rental-history').textContent);
  const urls = JSON.parse(document.getElementById('rental-urls').textContent);

  ReactDOM.createRoot(document.getElementById('rental-action-bar'))
    .render(<ActionBar rental={rental} urls={urls} />);

  ReactDOM.createRoot(document.getElementById('rental-tabs'))
    .render(<RentalTabs rental={rental} items={items} rooms={rooms}
                        issues={issues} history={history} urls={urls} />);
})();
