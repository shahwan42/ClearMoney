// Dark mode toggle with localStorage persistence.
// Uses Tailwind's class-based dark mode: <html class="dark">

(function() {
  const THEME_KEY = 'clearmoney-theme';

  function getPreference() {
    return localStorage.getItem(THEME_KEY) || 'light';
  }

  function applyTheme(theme) {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem(THEME_KEY, theme);

    // Update toggle button icon
    const btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.innerHTML = theme === 'dark' ? '☀️' : '🌙';
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
