import "bootstrap/js/dist/modal";
import "bootstrap/js/dist/collapse";
import "bootstrap/js/dist/alert";
import "bootstrap/js/dist/dropdown";
import Tooltip from "bootstrap/js/dist/tooltip";

import "bootstrap/dist/css/bootstrap.min.css";

document.addEventListener("DOMContentLoaded", function () {
  const tooltipTriggerList = document.querySelectorAll(
    "[data-bs-toggle='tooltip']"
  );

  [...tooltipTriggerList].map(
    (tooltipTriggerEl) => new Tooltip(tooltipTriggerEl)
  );

  tooltipTriggerList.forEach((tooltipTriggerEl) => {
    tooltipTriggerEl.style.cursor = "help";
  });
});
