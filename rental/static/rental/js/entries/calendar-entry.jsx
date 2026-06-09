(() => {
  const dateEl = document.getElementById('room-cal-date');
  if (!dateEl) {
    console.error('Date element not found');
    return;
  }
  const date = JSON.parse(dateEl.textContent);
  const root = document.getElementById('room-calendar-root');
  if (root) {
    ReactDOM.createRoot(root).render(<RoomCalendar date={date} />);
  }
})();
