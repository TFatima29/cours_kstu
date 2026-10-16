// Тема (светлая / тёмная / как в системе) и мобильное меню
(function () {
  var root = document.documentElement;

  function storedTheme() {
    try { return localStorage.getItem("cp-theme"); } catch (e) { return null; }
  }
  function saveTheme(value) {
    try { localStorage.setItem("cp-theme", value); } catch (e) { /* хранилище недоступно */ }
  }
  function currentTheme() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    var update = function () {
      var dark = currentTheme() === "dark";
      toggle.setAttribute("aria-label", dark ? "Включить светлую тему" : "Включить тёмную тему");
      toggle.setAttribute("aria-pressed", dark ? "true" : "false");
    };
    update();
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      saveTheme(next);
      update();
    });
  }

  var menuBtn = document.getElementById("menu-toggle");
  var nav = document.getElementById("main-nav");
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Закрыть меню пользователя по клику вне его
  document.addEventListener("click", function (event) {
    document.querySelectorAll(".user-menu[open]").forEach(function (menu) {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });

  // Подтверждение опасных действий
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) event.preventDefault();
    });
  });
})();
