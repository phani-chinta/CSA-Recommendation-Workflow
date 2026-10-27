(() => {
  const root = document.documentElement;
  const themeButton = document.querySelector("[data-theme-toggle]");
  const themeLabel = themeButton?.querySelector("[data-theme-label]");
  const themeMeta = document.querySelector('meta[name="theme-color"]');

  const applyTheme = (theme) => {
    const dark = theme === "dark";
    root.dataset.theme = dark ? "dark" : "light";
    if (themeMeta) themeMeta.content = dark ? "#111916" : "#f5f7f6";
    if (!themeButton) return;
    themeButton.setAttribute("aria-pressed", String(dark));
    themeButton.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    if (themeLabel) themeLabel.textContent = dark ? "Light mode" : "Dark mode";
  };

  try {
    const saved = localStorage.getItem("customer-signals-theme") || localStorage.getItem("signal-desk-theme");
    applyTheme(saved === "dark" ? "dark" : "light");
  } catch {
    applyTheme("light");
  }

  themeButton?.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("customer-signals-theme", next); } catch {}
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
    menuButton?.setAttribute("aria-expanded", String(Boolean(open)));
  });
  overlay?.addEventListener("click", closeMenu);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });
  sidebar?.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
})();