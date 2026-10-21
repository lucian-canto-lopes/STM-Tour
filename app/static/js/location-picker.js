(() => {
  const mode = document.getElementById('location-mode');
  const frame = document.getElementById('location-map');
  const container = document.getElementById('location-map-container');
  const fields = document.getElementById('location-coordinate-fields');
  const help = document.getElementById('location-map-help');
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
  function updateValidity() {
    const lat = parse(latitude), lng = parse(longitude);
    const valid = Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
    mode.setCustomValidity(mode.value === 'map' && !valid ? 'Selecione a localização do ponto no mapa.' : '');
  }
  function updateMode() {
    const useMap = mode.value === 'map';
    fields.hidden = useMap;
    help.hidden = !useMap;
    latitude.type = longitude.type = useMap ? 'hidden' : 'text';
    container.hidden = !useMap;
    status.textContent = '';
    updateValidity();
    if (!container.hidden) {
      // Recarrega ao reabrir para o Leaflet calcular o tamanho visível do mapa.
      frame.src = frame.dataset.src;
    }
  }
  mode.addEventListener('change', updateMode);
  updateMode();
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
    updateValidity();
    status.textContent = 'Localização selecionada. Você pode mover o marcador para ajustar.';
  });
})();
