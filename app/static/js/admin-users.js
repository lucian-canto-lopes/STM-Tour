(() => {
  const dialog = document.querySelector('.ban-dialog');
  if (!dialog) return;
  const form = dialog.querySelector('form');
  const duration = form.querySelector('.ban-duration');
  let returnFocus;
  const sync = () => {
    duration.hidden = form.elements.kind.value !== 'temporary';
    form.elements.days.disabled = duration.hidden;
  };
  document.querySelectorAll('[data-ban-url]').forEach(button => {
    button.addEventListener('click', () => {
      form.reset();
      sync();
      form.action = button.dataset.banUrl;
      dialog.querySelector('[data-ban-name]').textContent = button.dataset.userName;
      dialog.querySelector('[data-ban-email]').textContent = button.dataset.userEmail;
      returnFocus = button;
      dialog.showModal();
    });
  });
  form.elements.kind.addEventListener('change', sync);
  dialog.querySelectorAll('.ban-dialog-close, .ban-dialog-cancel').forEach(button => {
    button.addEventListener('click', () => dialog.close());
  });
  dialog.addEventListener('close', () => returnFocus?.focus());
  dialog.addEventListener('click', event => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right ||
        event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
  });
})();
