// Загрузка фото на экране «Описание повреждений»:
// превью выбранных фото, удаление крестиком, не больше MAX штук.
// Сами файлы лежат в <input type="file" name="photos"> — форма отправит их на сервер как есть (multipart/form-data).
(() => {
  const MAX = 6;
  const input = document.getElementById('photo-input');
  const list = document.getElementById('photos');
  const template = document.getElementById('photo-template');
  if (!input || !list || !template) return;

  const addSlot = list.querySelector('.photos__slot--add');   // слот с камерой: один на всех, переезжает на первое свободное место
  let files = [];   // выбранные файлы по порядку
  let urls = [];    // адреса превью; освобождаем при удалении

  // Отдаём input актуальный список: после удаления фото на сервер должны уйти только оставшиеся
  function syncInput() {
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
  }

  function render() {
    list.replaceChildren();
    for (let i = 0; i < MAX; i++) {
      if (i < files.length) {
        const slot = template.content.firstElementChild.cloneNode(true);
        const img = slot.querySelector('.photos__img');
        img.src = urls[i];
        img.alt = `Фото ${i + 1}`;
        slot.querySelector('.photos__remove').setAttribute('aria-label', `Удалить фото ${i + 1}`);
        list.append(slot);
      } else if (i === files.length) {
        list.append(addSlot);
      } else {
        const empty = document.createElement('li');
        empty.className = 'photos__slot';
        list.append(empty);
      }
    }
  }

  input.addEventListener('change', () => {
    const free = MAX - files.length;
    const added = [...input.files].filter((file) => file.type.startsWith('image/')).slice(0, free);
    added.forEach((file) => {
      files.push(file);
      urls.push(URL.createObjectURL(file));
    });
    syncInput();
    render();
  });

  list.addEventListener('click', (event) => {
    const button = event.target.closest('.photos__remove');
    if (!button) return;
    const index = [...list.children].indexOf(button.closest('.photos__slot'));
    URL.revokeObjectURL(urls[index]);
    files.splice(index, 1);
    urls.splice(index, 1);
    syncInput();
    render();
  });
})();
