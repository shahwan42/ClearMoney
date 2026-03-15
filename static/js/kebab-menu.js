// kebab-menu.js -- Kebab (3-dot) dropdown menu for transaction rows.
// Toggles a dropdown on click, closes on outside click or Escape.
// Re-initializes after HTMX swaps to handle dynamically loaded content.

var KebabMenu = (function () {
  "use strict";

  function closeAll() {
    document
      .querySelectorAll("[data-kebab-menu]:not(.hidden)")
      .forEach(function (menu) {
        menu.classList.add("hidden");
      });
  }

  function toggle(button) {
    var menu = button.nextElementSibling;
    if (!menu) return;

    var isOpen = !menu.classList.contains("hidden");
    closeAll();

    if (!isOpen) {
      menu.classList.remove("hidden");
    }
  }

  // Close on click outside
  document.addEventListener("click", function (e) {
    if (
      !e.target.closest("[data-kebab-trigger]") &&
      !e.target.closest("[data-kebab-menu]")
    ) {
      closeAll();
    }
  });

  // Close on Escape
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll();
  });

  // Close menus after HTMX swaps (e.g., after edit/delete)
  document.addEventListener("htmx:afterSettle", function () {
    closeAll();
  });

  return { toggle: toggle, closeAll: closeAll };
})();
