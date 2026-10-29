(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.add("js"); // CSS animations only apply when JavaScript is running
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var nav = document.querySelector(".nav");

  /* ---------- Theme toggle (remembers your choice) ---------- */
  var theme = "dark";
  try { theme = localStorage.getItem("aa360-theme") || theme; } catch (e) {}

  var actions = document.createElement("div");
  actions.className = "nav-actions";
  var btnTheme = document.createElement("button");
  btnTheme.type = "button";
  btnTheme.className = "icon-btn";
  var btnMenu = document.createElement("button");
  btnMenu.type = "button";
  btnMenu.className = "icon-btn menu-btn";
  btnMenu.textContent = "\u2630";
  btnMenu.setAttribute("aria-label", "Toggle menu");
  actions.appendChild(btnTheme);
  actions.appendChild(btnMenu);
  if (nav) nav.appendChild(actions);

  function applyTheme(t) {
    theme = t;
    root.setAttribute("data-theme", t);
    btnTheme.textContent = t === "dark" ? "\u2600" : "\u263E";
    btnTheme.setAttribute("aria-label", t === "dark" ? "Switch to light theme" : "Switch to dark theme");
    try { localStorage.setItem("aa360-theme", t); } catch (e) {}
  }
  applyTheme(theme);
  btnTheme.addEventListener("click", function () { applyTheme(theme === "dark" ? "light" : "dark"); });

  /* ---------- Mobile menu ---------- */
  btnMenu.addEventListener("click", function () {
    var open = nav.classList.toggle("open");
    btnMenu.setAttribute("aria-expanded", open ? "true" : "false");
  });
  var navLinks = [].slice.call(document.querySelectorAll(".links a"));
  navLinks.forEach(function (a) {
    a.addEventListener("click", function () { nav.classList.remove("open"); });
  });

  /* ---------- Scroll progress bar ---------- */
  var bar = document.createElement("div");
  bar.className = "progress";
  document.body.appendChild(bar);
  function onScroll() {
    var h = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.transform = "scaleX(" + (h > 0 ? window.scrollY / h : 0) + ")";
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- Count-up numbers (90, 85.6%, 0.166 ...) ---------- */
  function countUp(el) {
    var m = /^([\d.]+)(.*)$/.exec(el.textContent.trim());
    if (!m) return;
    var end = parseFloat(m[1]);
    var suffix = m[2];
    var dec = (m[1].split(".")[1] || "").length;
    var t0 = null;
    function step(ts) {
      if (t0 === null) t0 = ts;
      var p = Math.min((ts - t0) / 1200, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (end * eased).toFixed(dec) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* ---------- Reveal on scroll ---------- */
  if ("IntersectionObserver" in window) {
    var targets = document.querySelectorAll(".section h2, .section .narrow, .card, .steps li, .stat, .table");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        el.classList.add("in");
        io.unobserve(el);
        if (!reduce && el.classList.contains("stat")) {
          var num = el.querySelector(".num");
          if (num) countUp(num);
        }
        // Tidy up afterwards so hover effects work normally
        setTimeout(function () {
          el.classList.remove("reveal", "in");
          el.style.transitionDelay = "";
        }, 1500);
      });
    }, { threshold: 0.12 });

    [].forEach.call(targets, function (el) {
      var idx = Array.prototype.indexOf.call(el.parentNode.children, el);
      el.style.transitionDelay = Math.min(idx, 6) * 70 + "ms";
      el.classList.add("reveal");
      io.observe(el);
    });

    /* ---------- Highlight the current section in the nav ---------- */
    var byId = {};
    var sections = [];
    navLinks.forEach(function (a) {
      var id = (a.getAttribute("href") || "").slice(1);
      var s = document.getElementById(id);
      if (s) { byId[id] = a; sections.push(s); }
    });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        navLinks.forEach(function (l) { l.classList.remove("active"); });
        if (byId[en.target.id]) byId[en.target.id].classList.add("active");
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    sections.forEach(function (s) { spy.observe(s); });
  }

  /* ---------- Spotlight follows the mouse on cards ---------- */
  [].forEach.call(document.querySelectorAll(".card, .stat"), function (el) {
    el.addEventListener("pointermove", function (e) {
      var r = el.getBoundingClientRect();
      el.style.setProperty("--mx", e.clientX - r.left + "px");
      el.style.setProperty("--my", e.clientY - r.top + "px");
    });
  });
})();