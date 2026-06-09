(() => {
  const initial = JSON.parse(document.getElementById('wizard-initial').textContent);
  ReactDOM.createRoot(document.getElementById('wizard-root'))
          .render(<WizardScreen initial={initial} />);
})();
