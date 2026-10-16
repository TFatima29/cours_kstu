// «Трасса»: курс рисуется как гоночная трасса. Сектор — уровень, поворот — урок.
// Форма трассы своя у каждого курса (зависит от id), машинка проезжает круг.
(function () {
  var NS = "http://www.w3.org/2000/svg";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function rng(seed) {
    var s = (seed * 9301 + 49297) % 233280 || 1;
    return function () { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  }

  // замкнутая трасса: точки вокруг эллипса со случайными «шпильками», сглаженные Catmull-Rom
  function circuitPath(seed, corners, w, h, pad) {
    var r = rng(seed + 7), n = Math.max(7, Math.min(corners + 3, 16)), pts = [];
    for (var i = 0; i < n; i++) {
      var a = (i / n) * Math.PI * 2 + (r() - 0.5) * 0.35;
      var k = 0.62 + r() * 0.38;
      if (i % 3 === 1) k *= 0.6 + r() * 0.25; // внутренний поворот
      pts.push([w / 2 + Math.cos(a) * (w / 2 - pad) * k, h / 2 + Math.sin(a) * (h / 2 - pad) * k]);
    }
    var d = "M" + pts[0][0].toFixed(1) + "," + pts[0][1].toFixed(1);
    for (var j = 0; j < n; j++) {
      var p0 = pts[(j - 1 + n) % n], p1 = pts[j], p2 = pts[(j + 1) % n], p3 = pts[(j + 2) % n];
      var c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      var c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      d += " C" + c1.map(f).join(",") + " " + c2.map(f).join(",") + " " + p2.map(f).join(",");
    }
    return d + " Z";
  }
  function f(v) { return v.toFixed(1); }
  function plural(n, forms) {
    var a = Math.abs(n) % 100, b = a % 10;
    if (a > 10 && a < 20) return forms[2];
    if (b > 1 && b < 5) return forms[1];
    if (b === 1) return forms[0];
    return forms[2];
  }

  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) {
      // var(--…) работает только в style, не в атрибутах SVG
      if ((k === "fill" || k === "stroke") && String(attrs[k]).indexOf("var(") === 0) e.style[k] = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    if (parent) parent.appendChild(e);
    return e;
  }

  // ---------- маленькие трассы на обложках ----------
  document.querySelectorAll("svg.mini-circuit").forEach(function (svg) {
    var seed = parseInt(svg.dataset.seed || "1", 10);
    var lessons = parseInt(svg.dataset.lessons || "6", 10);
    var d = circuitPath(seed, lessons, 320, 180, 18);
    el("path", { d: d, class: "road" }, svg);
    el("path", { d: d, class: "kerb" }, svg);
  });

  // ---------- большая трасса в герое ----------
  var box = document.getElementById("circuit");
  var dataEl = document.getElementById("hero-courses");
  if (!box || !dataEl) return;
  var courses = JSON.parse(dataEl.textContent || "[]");
  if (!courses.length) { box.hidden = true; return; }
  var svg = document.getElementById("circuit-svg");
  var W = 600, H = 330, car, road, total = 0, raf = null, start = null;

  function draw(course) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var d = circuitPath(course.id, course.lessons, W, H, 22);
    el("path", { d: d, fill: "none", stroke: "var(--surface-2)", "stroke-width": 34, "stroke-linejoin": "round" }, svg);
    road = el("path", { d: d, fill: "none", stroke: "var(--ink)", "stroke-width": 18, "stroke-linejoin": "round" }, svg);
    el("path", { d: d, fill: "none", stroke: "var(--lime)", "stroke-width": 2, "stroke-dasharray": "10 12" }, svg);
    total = road.getTotalLength();

    // старт-финиш: шахматная полоса
    var p0 = road.getPointAtLength(0), p1 = road.getPointAtLength(2);
    var ang = Math.atan2(p1.y - p0.y, p1.x - p0.x) * 180 / Math.PI;
    var flag = el("g", { transform: "translate(" + f(p0.x) + "," + f(p0.y) + ") rotate(" + f(ang) + ")" }, svg);
    for (var fx = 0; fx < 2; fx++) for (var fy = 0; fy < 4; fy++) {
      el("rect", { x: -6 + fx * 6, y: -12 + fy * 6, width: 6, height: 6, fill: (fx + fy) % 2 ? "var(--ink)" : "#fff" }, flag);
    }

    // секторы-уровни: граница пропорциональна числу уроков в уровне
    var sectors = course.sectors.length ? course.sectors : [{ title: "", lessons: course.lessons || 1 }];
    var lessonsSum = sectors.reduce(function (a, s) { return a + Math.max(s.lessons, 1); }, 0);
    var acc = 0, lessonIndex = 0, totalLessons = sectors.reduce(function (a, s) { return a + s.lessons; }, 0);
    sectors.forEach(function (s, i) {
      var at = (acc / lessonsSum) * total;
      var p = road.getPointAtLength(at);
      var g = el("g", { transform: "translate(" + f(p.x) + "," + f(p.y) + ")" }, svg);
      el("rect", { x: -11, y: -11, width: 22, height: 22, transform: "rotate(45)", fill: i === 0 ? "var(--lime)" : "var(--surface)", stroke: "var(--ink)", "stroke-width": 2.5 }, g);
      var t = el("text", { "text-anchor": "middle", dy: "4.5", class: "circuit-sector-label" }, g);
      t.textContent = String(i + 1);
      var title = el("title", {}, g);
      title.textContent = "Уровень " + (i + 1) + ": " + s.title;
      acc += Math.max(s.lessons, 1);
    });
    // повороты-уроки
    for (var L = 0; L < totalLessons; L++) {
      var pp = road.getPointAtLength(((L + 0.5) / Math.max(totalLessons, 1)) * total);
      el("circle", { cx: f(pp.x), cy: f(pp.y), r: 3.2, fill: "var(--surface)" }, svg);
    }

    car = el("g", {}, svg);
    el("circle", { r: 11, fill: "var(--lime)", stroke: "var(--ink)", "stroke-width": 3 }, car);
    el("circle", { r: 3, fill: "var(--ink)" }, car);
    placeCar(0);

    document.getElementById("c-levels").textContent = course.levels;
    document.getElementById("c-lessons").textContent = course.lessons;
    document.getElementById("c-levels-w").textContent = plural(course.levels, ["сектор-уровень", "сектора-уровня", "секторов-уровней"]);
    document.getElementById("c-lessons-w").textContent = plural(course.lessons, ["поворот-урок", "поворота-урока", "поворотов-уроков"]);
    var link = document.getElementById("c-link");
    link.href = course.url;
    link.textContent = "Открыть «" + course.title + "»";
    start = null;
  }

  function placeCar(frac) {
    var p = road.getPointAtLength((frac % 1) * total);
    car.setAttribute("transform", "translate(" + f(p.x) + "," + f(p.y) + ")");
  }

  function tick(ts) {
    if (start === null) start = ts;
    var lap = 7000; // круг за 7 секунд, на прямых машинка быстрее за счёт плавного ускорения
    var t = ((ts - start) % lap) / lap;
    placeCar(t - Math.sin(t * Math.PI * 2) * 0.03);
    raf = requestAnimationFrame(tick);
  }

  var buttons = box.querySelectorAll(".circuit-pick button");
  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      buttons.forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      draw(courses[parseInt(b.dataset.i, 10)]);
    });
  });

  draw(courses[0]);
  if (!reduce) {
    var visible = true;
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (e) {
        visible = e[0].isIntersecting;
        if (visible && !raf) raf = requestAnimationFrame(tick);
        if (!visible && raf) { cancelAnimationFrame(raf); raf = null; }
      }).observe(box);
    } else {
      raf = requestAnimationFrame(tick);
    }
  }
})();
