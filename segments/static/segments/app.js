(() => {
  const root = document.documentElement;
  const themeButton = document.querySelector("[data-theme-toggle]");
  const themeIcon = themeButton?.querySelector("use");

  const applyTheme = (theme) => {
    root.dataset.theme = theme;
    if (themeIcon) themeIcon.setAttribute("href", theme === "dark" ? "#i-sun" : "#i-moon");
    if (themeButton) {
      const label = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
      themeButton.setAttribute("aria-label", label);
      themeButton.title = label;
    }
  };

  try {
    applyTheme(localStorage.getItem("signal-desk-theme") || "light");
  } catch {
    applyTheme("light");
  }

  themeButton?.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("signal-desk-theme", next); } catch {}
  });

  const sidebar = document.getElementById("sidebar");
  const overlay = document.querySelector("[data-overlay]");
  const menuButton = document.querySelector("[data-menu-toggle]");
  const closeMenu = () => {
    sidebar?.classList.remove("open");
    overlay?.classList.remove("visible");
    menuButton?.setAttribute("aria-expanded", "false");
  };
  menuButton?.addEventListener("click", () => {
    const open = sidebar?.classList.toggle("open");
    overlay?.classList.toggle("visible", Boolean(open));
    menuButton.setAttribute("aria-expanded", String(Boolean(open)));
  });
  overlay?.addEventListener("click", closeMenu);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });
  sidebar?.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
})();
