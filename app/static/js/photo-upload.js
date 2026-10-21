(() => {
  const input = document.getElementById('photo');
  const preview = document.getElementById('photo-preview');
  const title = document.getElementById('photo-upload-title');
  const selection = document.getElementById('photo-selection');
  const action = document.querySelector('.photo-upload-action');
  let previewUrl;

  function update() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = undefined;
    const file = input.files[0];
    preview.hidden = true;
    preview.removeAttribute('src');
    input.closest('.photo-upload-area').classList.toggle('has-photo', Boolean(file));
    title.textContent = file ? 'Foto selecionada' : 'Adicione uma foto';
    selection.textContent = file ? file.name : 'Toque para selecionar da sua galeria';
    action.textContent = file ? 'Trocar foto ↗' : 'Selecionar foto ↑';
    if (file && ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      previewUrl = URL.createObjectURL(file);
      preview.src = previewUrl;
      preview.hidden = false;
    }
  }

  input.addEventListener('change', update);
  input.form.addEventListener('reset', () => setTimeout(update, 0));
  preview.addEventListener('error', () => { preview.hidden = true; });
})();
