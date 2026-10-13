document.querySelectorAll('[data-star-rating]').forEach((container) => {
  const track = container.querySelector('[role="slider"]');
  const input = container.querySelector('input[name="rating"]');
  function paint(value) {
    track.style.setProperty('--rating-fill', `${value * 20}%`);
  }
  function sync() {
    const value = Number(input.value);
    const valid = input.value !== '' && value >= 0.5 && value <= 5 && Number.isInteger(value * 2);
    paint(valid ? value : 0);
    // Keep the accessible slider value within its range before selection.
    track.setAttribute('aria-valuenow', valid ? value : 0.5);
    track.setAttribute('aria-valuetext', valid ? `${String(value).replace('.', ',')} de 5 estrelas` : 'Nenhuma nota selecionada');
  }
  function positionValue(event) {
    const rect = track.getBoundingClientRect();
    return Math.max(0.5, Math.min(5, Math.ceil(((event.clientX - rect.left) / rect.width) * 10) / 2));
  }
  function choose(value) {
    input.value = value;
    sync();
  }
  track.addEventListener('pointermove', (event) => {
    if (event.pointerType === 'mouse') paint(positionValue(event));
  });
  track.addEventListener('pointerleave', sync);
  track.addEventListener('click', (event) => choose(positionValue(event)));
  track.addEventListener('keydown', (event) => {
    let value = Number(input.value) || 0;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') value += 0.5;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') value -= 0.5;
    else if (event.key === 'Home') value = 0.5;
    else if (event.key === 'End') value = 5;
    else return;
    event.preventDefault();
    choose(Math.max(0.5, Math.min(5, value)));
  });
  input.addEventListener('input', sync);
  sync();
});
