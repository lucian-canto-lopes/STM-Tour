(() => {
  const tablist = document.querySelector('.place-tabs');
  if (!tablist) return;
  const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
  const panels = tabs.map(tab => document.getElementById(tab.getAttribute('aria-controls')));
  let selected = 0;

  function select(id, { focus = false, updateHash = false } = {}) {
    const index = panels.findIndex(panel => panel.id === id);
    if (index < 0) return;
    selected = index;
    tabs.forEach((tab, i) => {
      tab.setAttribute('aria-selected', String(i === index));
      tab.tabIndex = i === index ? 0 : -1;
      panels[i].hidden = i !== index;
    });
    if (focus) tabs[index].focus();
    if (updateHash) history.replaceState(null, '', `#${id}`);
  }

  tablist.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    let index = selected;
    if (event.key === 'Home') index = 0;
    else if (event.key === 'End') index = tabs.length - 1;
    else index = (selected + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    select(panels[index].id, { focus: true, updateHash: true });
  });

  document.querySelectorAll('.place-tabs a, .rating-summary').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      select(link.hash.slice(1), { updateHash: true });
    });
  });

  panels.forEach(panel => {
    let start = null;
    panel.addEventListener('touchstart', event => {
      start = event.touches.length === 1 && !event.target.closest('input, textarea, button, a, summary, [role="slider"]')
        ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null;
    }, { passive: true });
    panel.addEventListener('touchend', event => {
      if (!start) return;
      const dx = event.changedTouches[0].clientX - start.x;
      const dy = event.changedTouches[0].clientY - start.y;
      start = null;
      if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      const next = selected + (dx < 0 ? 1 : -1);
      if (next >= 0 && next < panels.length) select(panels[next].id, { updateHash: true });
    }, { passive: true });
    panel.addEventListener('touchcancel', () => { start = null; }, { passive: true });
  });

  window.addEventListener('hashchange', () => select(location.hash.slice(1) || 'sobre'));
  const initial = tablist.dataset.initialTab;
  select(initial !== 'sobre' ? initial : (location.hash.slice(1) || 'sobre'));
})();
