document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("is-public-form");
  if (!form) { return; }
  form.addEventListener("change", function () {
    let url = new URL(window.location.href);
    url = url.origin + url.pathname + "is-public/";
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": form.querySelector("input[name=csrfmiddlewaretoken]").value,
      },
    }).then(function () {
      window.location.reload();
    });
  });
});
