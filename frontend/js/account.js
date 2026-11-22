const page = location.pathname.split("/").pop();
const form = document.querySelector("form");
const notice = document.createElement("p");
notice.setAttribute("role", "status");
(form || document.querySelector("main") || document.body).append(notice);

let refreshPending;

async function renewSession() {
  const refresh = () => fetch("/api/v1/auth/refresh", {method: "POST"});
  if (!refreshPending) {
    // Tabs share cookies. Serialize rotations so each request uses the latest token.
    const request = navigator.locks ? navigator.locks.request("users-session-refresh", refresh) : refresh();
    refreshPending = request.finally(() => { refreshPending = undefined; });
  }
  return refreshPending;
}

async function api(path, body, method = body === undefined ? "GET" : "POST") {
  const options = {method};
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers = {"Content-Type": "application/json"};
    options.body = JSON.stringify(body);
  }
  let response = await fetch("/api/v1/" + path, options);
  if (response.status === 401 && !path.startsWith("auth/")) {
    const renewed = await renewSession();
    if (renewed.ok) {
      response = await fetch("/api/v1/" + path, options);
    } else if (renewed.status !== 401) {
      throw new Error("Не удалось продлить сессию. Попробуйте ещё раз.");
    }
  }
  if (response.status === 204) return;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !["login.html","registration.html"].includes(page)) {
      location.assign("login.html");
    }
    throw new Error(typeof data.detail === "string" ? data.detail : "Проверьте поля формы.");
  }
  return data;
}

let currentDraft;
let photoControls;
let submitting = false;
const editable = status => ["draft", "needs_clarification", "error"].includes(status);
const statusNames = {
  draft: "Черновик", queued: "В очереди", processing: "Обрабатывается",
  needs_clarification: "Требуется уточнение", ready: "Материалы проверены", error: "Ошибка обработки"
};

function showAssessment() {
  const canEdit = editable(currentDraft.status) && !submitting;
  const busy = photoControls?.busy() ?? true;
  form.elements.description.disabled = !canEdit;
  form.querySelector('button[type="submit"]:not(#calculate)').disabled = !canEdit || busy;
  form.querySelector("#calculate").disabled = !canEdit || busy;
  photoControls?.setEditable(canEdit);
  document.getElementById("assessment-status").textContent =
    [statusNames[currentDraft.status], currentDraft.result_note].filter(Boolean).join(". ");
}

function pollAssessment() {
  if (!["queued", "processing"].includes(currentDraft.status)) return;
  setTimeout(async () => {
    try {
      currentDraft = await api("assessments/" + currentDraft.assessment_id);
      showAssessment();
      notice.textContent = "";
    } catch (error) {
      notice.textContent = error.message;
    }
    pollAssessment();
  }, 1500);
}

async function loadDraft() {
  const params = new URLSearchParams(location.search);
  const assessmentId = params.get("assessment_id");
  const carId = params.get("car_id") || sessionStorage.getItem("car_id");
  if (!assessmentId && !carId) {
    location.replace("cabinet.html");
    return;
  }
  currentDraft = assessmentId
    ? await api("assessments/" + encodeURIComponent(assessmentId))
    : await api("assessments", {car_id: carId});
  history.replaceState(null, "", "?assessment_id=" + encodeURIComponent(currentDraft.assessment_id));
  form.elements.description.value = currentDraft.description;

  const {setupPhotos} = await import("./photos.js");
  photoControls = await setupPhotos(currentDraft.assessment_id, api, showAssessment);
  showAssessment();
  pollAssessment();
}

if (page === "damage.html") {
  loadDraft().catch(error => notice.textContent = error.message);
}

const actions = {
  async "registration.html"(data) {
    await api("auth/register", data);
    sessionStorage.setItem("pendingEmail", data.email);
    location.assign("registration-confirm.html");
  },
  async "registration-confirm.html"(data) {
    await api("auth/confirm", {...data, email: sessionStorage.getItem("pendingEmail")});
    location.assign("login.html");
  },
  async "login.html"(data) {
    await api("auth/login", data);
    location.assign("cabinet.html");
  },
  async "recovery.html"(data) {
    if (data.password !== data["password-confirm"]) throw new Error("Пароли различаются.");
    await api("auth/reset-password", {...data, email: sessionStorage.getItem("pendingEmail")});
    location.assign("login.html");
  },
  async "car-data.html"(data) {
    const car = await api("cars", {make: data.brand.trim(), model: data.model.trim(),
      year: Number(data.year), mileage_km: Number(data.mileage), region: data.region.trim()});
    sessionStorage.setItem("car_id", car.id);
    location.assign("damage.html?car_id=" + encodeURIComponent(car.id));
  },
  async "damage.html"(data, button) {
    if (!currentDraft || submitting || !editable(currentDraft.status) || photoControls?.busy()) return;
    if (button?.id === "calculate") {
      submitting = true;
      showAssessment();
      try {
        currentDraft = await api("assessments/" + currentDraft.assessment_id + "/calculate", {
          description: data.description, version: currentDraft.version
        });
        notice.textContent = "";
        pollAssessment();
      } finally {
        submitting = false;
      }
      return;
    }
    currentDraft = await api("assessments/" + currentDraft.assessment_id, {
      description: data.description, version: currentDraft.version
    }, "PATCH");
    notice.textContent = "Описание сохранено в черновике.";
  }
};

form?.addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.submitter;
  if (button) button.disabled = true;
  try {
    await actions[page](Object.fromEntries(new FormData(form)), button);
  } catch (error) {
    notice.textContent = error.message;
  } finally {
    if (page === "damage.html" && currentDraft) showAssessment();
    else if (button) button.disabled = false;
  }
});

document.querySelector(".login__forgot")?.addEventListener("click", async event => {
  event.preventDefault();
  const email = form.elements.email;
  if (!email.reportValidity()) return;
  try {
    await api("auth/recovery", {email: email.value});
    sessionStorage.setItem("pendingEmail", email.value);
    location.assign("recovery.html");
  } catch (error) { notice.textContent = error.message; }
});

async function loadCabinet() {
  const [profile, cars] = await Promise.all([api("users/me"), api("cars")]);
  document.querySelector(".cabinet__value").textContent = profile.email;
  const list = document.querySelector("#saved-list");
  let drafts = [];
  try {
    drafts = await api("assessments?include_history=true");
  } catch (error) {
    notice.textContent = error.message;
  }
  const byCar = new Map(drafts.filter(item => item.status === "draft").map(item => [item.car_id, item]));
  for (const car of cars) {
    const item = document.createElement("li");
    item.className = "doc";
    const link = document.createElement("a");
    const draft = byCar.get(car.id);
    link.href = draft ? "damage.html?assessment_id=" + encodeURIComponent(draft.assessment_id)
      : "damage.html?car_id=" + encodeURIComponent(car.id);
    link.textContent = [car.make, car.model, car.year, car.region].join(" · ");
    if (draft) link.textContent += " · Продолжить черновик";
    item.append(link);
    list.append(item);
  }
  const carNames = new Map(cars.map(car => [car.id, [car.make, car.model, car.year].join(" ")]));
  for (const draft of drafts.filter(item => item.status !== "draft")) {
    const item = document.createElement("li");
    item.className = "doc";
    const link = document.createElement("a");
    link.href = "damage.html?assessment_id=" + encodeURIComponent(draft.assessment_id);
    link.textContent = [carNames.get(draft.car_id), statusNames[draft.status], draft.description.slice(0, 60)]
      .filter(Boolean).join(" · ");
    item.append(link);
    list.append(item);
  }
  document.querySelector("#saved-empty").hidden = cars.length > 0;
}
if (page === "cabinet.html") {
  loadCabinet().catch(error => notice.textContent = error.message);
  document.querySelector("[data-logout]").addEventListener("click", async event => {
    event.preventDefault();
    try {
      await api("auth/logout", {});
      sessionStorage.removeItem("car_id");
      location.assign("login.html");
    } catch (error) { notice.textContent = error.message; }
  });
}
