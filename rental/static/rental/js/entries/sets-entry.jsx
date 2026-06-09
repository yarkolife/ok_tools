(() => {
  const initial = JSON.parse(document.getElementById('sets-initial').textContent);
  ReactDOM.createRoot(document.getElementById('sets-root'))
          .render(<EquipmentSetsScreen initial={initial} />);
})();
