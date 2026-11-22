export async function setupPhotos(assessmentId, api, onBusyChange) {
  const path = "assessments/" + assessmentId + "/photos";
  const input = document.getElementById("photo-input");
  const list = document.getElementById("photos");
  const template = document.getElementById("photo-template");
  const addSlot = list.querySelector(".photos__slot--add");
  const status = document.getElementById("photo-status");
  let photos = await api(path);
  let busy = false;
  let editable = false;

  function render() {
    list.replaceChildren();
    for (const [index, photo] of photos.entries()) {
      const slot = template.content.firstElementChild.cloneNode(true);
      const img = slot.querySelector("img");
      img.src = "/api/v1/" + path + "/" + photo.photo_id;
      img.alt = "Фото повреждения " + (index + 1);
      const remove = slot.querySelector("button");
      remove.dataset.id = photo.photo_id;
      remove.disabled = busy || !editable;
      remove.setAttribute("aria-label", "Удалить фото " + (index + 1));
      list.append(slot);
    }
    input.disabled = !editable || busy || photos.length >= 6;
    if (editable && photos.length < 6) list.append(addSlot);
    while (list.children.length < 6) {
      const empty = document.createElement("li");
      empty.className = "photos__slot";
      list.append(empty);
    }
  }

  async function change(message, operation) {
    if (!editable || busy) return;
    busy = true;
    onBusyChange();
    render();
    status.textContent = message;
    try {
      await operation();
      status.textContent = "";
    } catch (error) {
      status.textContent = error.message;
    } finally {
      try {
        photos = await api(path);
      } catch (error) {
        status.textContent = error.message;
      }
      busy = false;
      onBusyChange();
      render();
    }
  }

  input.addEventListener("change", () => {
    const files = Array.from(input.files);
    input.value = "";
    change("Сохраняем фотографии…", async () => {
      for (const file of files) {
        if (file.size > 8 * 1024 * 1024) throw new Error("Максимальный размер фотографии — 8 МБ.");
        const data = new FormData();
        data.append("file", file);
        await api(path, data);
      }
    });
  });
  list.addEventListener("click", event => {
    const button = event.target.closest("button[data-id]");
    if (button) change("Удаляем фото…", () => api(path + "/" + button.dataset.id, undefined, "DELETE"));
  });
  render();
  return {
    busy: () => busy,
    setEditable(value) {
      if (editable !== value) {
        editable = value;
        render();
      }
    }
  };
}
