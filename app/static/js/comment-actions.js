(() => {
  const dialog = document.querySelector('.report-dialog');
  if (dialog) {
    let returnFocus;
    const form = dialog.querySelector('form');
    const other = form.querySelector('.report-other');
    const text = other.querySelector('textarea');
    const syncReason = () => {
      const isOther = form.elements.reason_category.value === 'other';
      other.hidden = !isOther;
      text.disabled = !isOther;
      text.required = isOther;
    };
    document.querySelectorAll('[data-report-url]').forEach(button => {
      button.addEventListener('click', () => {
        form.reset();
        syncReason();
        form.action = button.dataset.reportUrl;
        returnFocus = button.closest('.comment-menu').querySelector('summary');
        dialog.showModal();
        button.closest('.comment-menu').open = false;
      });
    });
    form.addEventListener('change', syncReason);
    dialog.addEventListener('close', () => returnFocus?.focus());
    dialog.querySelector('.report-close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', event => {
      const rect = dialog.getBoundingClientRect();
      if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right ||
          event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
    });
  }
  const menus = [...document.querySelectorAll('.comment-menu')];
  menus.forEach(menu => {
    menu.addEventListener('toggle', () => {
      if (menu.open) menus.forEach(other => { if (other !== menu) other.open = false; });
    });
    menu.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.open) {
        menu.open = false;
        menu.querySelector('summary').focus();
      }
    });
  });
  document.addEventListener('click', event => {
    menus.forEach(menu => { if (!menu.contains(event.target)) menu.open = false; });
  });
})();
