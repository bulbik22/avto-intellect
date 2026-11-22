const page = location.pathname.split("/").pop();
const form = document.querySelector("form");
const notice = document.createElement("p");
notice.setAttribute("role", "status");
(form || document.querySelector("main") || document.body).append(notice);

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  };
  const response = await fetch("/api/v1/" + path, options);
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !["login.html","registration.html"].includes(page)) {
      location.assign("login.html");
    }
    throw new Error(typeof data.detail === "string" ? data.detail : "Проверьте поля формы.");
  }
  return data;
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
    location.assign("damage.html");
  }
};

form?.addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.submitter;
  if (button) button.disabled = true;
  try {
    await actions[page](Object.fromEntries(new FormData(form)));
  } catch (error) {
    notice.textContent = error.message;
  } finally {
    if (button) button.disabled = false;
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
  for (const car of cars) {
    const item = document.createElement("li");
    item.className = "doc";
    const link = document.createElement("a");
    link.href = "damage.html";
    link.textContent = [car.make, car.model, car.year, car.region].join(" · ");
    link.addEventListener("click", () => sessionStorage.setItem("car_id", car.id));
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
