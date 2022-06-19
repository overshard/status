import Cookie from "js-cookie";

const cookieWarningEl = document.querySelector("#cookie-warning");
const cookieWarningCookieName = "cookie-warning-accepted";

if (!Cookie.get(cookieWarningCookieName)) {
  cookieWarningEl.classList.add("show");
  const cookieWarningButtonEl = cookieWarningEl.querySelector("button");
  cookieWarningButtonEl.addEventListener("click", () => {
    Cookie.set(cookieWarningCookieName, "true", { expires: 365 });
  });
}
