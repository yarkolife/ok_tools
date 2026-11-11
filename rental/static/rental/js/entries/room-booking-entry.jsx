/* Week and month room calendars: any element with data-book-room and
   data-book-date opens the "Reserve room" dialog for that room and day. */
(() => {
  const root = document.getElementById('room-booking-root');
  if (!root) return;
  ReactDOM.createRoot(root).render(<RoomBookingLauncher />);

  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-book-room]');
    if (!el || e.target.closest('a[href]')) return;
    e.preventDefault();
    if (window.openRoomBooking) window.openRoomBooking(el.dataset.bookRoom, el.dataset.bookDate);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const el = e.target.closest('[data-book-room]');
    if (!el || e.target !== el) return;
    e.preventDefault();
    if (window.openRoomBooking) window.openRoomBooking(el.dataset.bookRoom, el.dataset.bookDate);
  });
})();
