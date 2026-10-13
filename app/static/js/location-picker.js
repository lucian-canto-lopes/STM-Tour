(() => {
  const mode = document.getElementById('location-mode');
  const frame = document.getElementById('location-map');
  const container = document.getElementById('location-map-container');
  const latitude = document.getElementById('latitude');
  const longitude = document.getElementById('longitude');
  const status = document.getElementById('location-status');
  const parse = input => input.value.trim() ? Number(input.value.replace(',', '.')) : NaN;
  function sync() {
    const lat = parse(latitude), lng = parse(longitude);
    if (Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180) {
      frame.contentWindow?.postMessage({type: 'location-set', latitude: lat, longitude: lng}, location.origin);
    }
  }
  mode.addEventListener('change', () => {
    container.hidden = mode.value !== 'map';
    if (!container.hidden) {
      // Recarrega ao reabrir para o Leaflet calcular o tamanho visível do mapa.
      frame.src = frame.dataset.src;
    }
  });
  latitude.addEventListener('change', sync);
  longitude.addEventListener('change', sync);
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
    if (event.data?.type === 'location-ready') sync();
    if (event.data?.type !== 'location-selected') return;
    const {latitude: lat, longitude: lng} = event.data;
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return;
    latitude.value = lat.toFixed(6);
    longitude.value = lng.toFixed(6);
    status.textContent = `Local selecionado: ${latitude.value}, ${longitude.value}`;
  });
})();
