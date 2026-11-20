// Личный кабинет: удаление документов и черновиков, выход из аккаунта.
// Все обращения к серверу — в объекте api ниже: когда бэкенд будет готов, правится только он.
(() => {
  const api = {
    // Удалить документ или черновик. Должна выбросить ошибку, если сервер не удалил.
    async deleteDocument(id) {
      // await fetch(`/api/documents/${id}`, { method: 'DELETE', credentials: 'include' }).then(checkOk);
    },
    // Выйти из аккаунта (сбросить сессию на сервере)
    async logout() {
      // await fetch('/api/logout', { method: 'POST', credentials: 'include' }).then(checkOk);
    },
  };

  const CONFIRM_MS = 3000;   // сколько секунд кнопка ждёт подтверждения удаления
  const list = document.getElementById('saved-list');
  const empty = document.getElementById('saved-empty');
  const logout = document.querySelector('[data-logout]');

  // Удаление в два нажатия: первое меняет надпись на «Точно удалить?», второе удаляет.
  // Случайное нажатие пальцем на мобильном не стирает документ.
  function resetConfirm(button) {
    clearTimeout(button.confirmTimer);
    button.classList.remove('is-confirm');
    button.textContent = 'Удалить';
    button.disabled = false;
  }

  list?.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-doc-delete]');
    if (!button) return;

    if (!button.classList.contains('is-confirm')) {
      button.classList.add('is-confirm');
      button.textContent = 'Точно удалить?';
      button.confirmTimer = setTimeout(() => resetConfirm(button), CONFIRM_MS);
      return;
    }

    clearTimeout(button.confirmTimer);
    const item = button.closest('.doc');
    button.disabled = true;
    button.textContent = 'Удаляем…';
    try {
      await api.deleteDocument(item.dataset.id);
    } catch (error) {
      resetConfirm(button);
      button.textContent = 'Не удалось, ещё раз';
      return;
    }
    item.remove();
    if (empty) empty.hidden = list.children.length > 0;
  });

  // Без JS ссылка просто ведёт на страницу входа; с JS сначала закрываем сессию на сервере
  logout?.addEventListener('click', async (event) => {
    event.preventDefault();
    try {
      await api.logout();
    } finally {
      window.location.href = logout.href;
    }
  });
})();
