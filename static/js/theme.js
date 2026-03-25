// Dark mode toggle with localStorage persistence.
// Uses Tailwind's class-based dark mode: <html class="dark">

(function() {
  const THEME_KEY = 'clearmoney-theme';

  function getPreference() {
    var saved = localStorage.getItem(THEME_KEY);
    if (saved) return saved;
    // First visit: respect OS prefers-color-scheme preference
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem(THEME_KEY, theme);

    // Update header toggle button icon and aria-pressed state
    const btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.innerHTML = theme === 'dark' ? '☀️' : '🌙';
      btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    }

    // Update settings page toggle button (if present)
    const settingsBtn = document.getElementById('settings-theme-toggle');
    if (settingsBtn) {
      var label = settingsBtn.querySelector('#settings-theme-label');
      var icon = settingsBtn.querySelector('#settings-theme-icon');
      if (label) label.textContent = theme === 'dark' ? 'Disable Dark Mode' : 'Enable Dark Mode';
      if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
      settingsBtn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    }
  }

  // Apply saved preference immediately (before DOM renders)
  applyTheme(getPreference());

  // Expose toggle function globally
  window.toggleTheme = function() {
    const current = getPreference();
    applyTheme(current === 'dark' ? 'light' : 'dark');
  };
})();
