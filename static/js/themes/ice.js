// «Лёд»: поле кристаллов. Каждый крупный кристалл — опубликованный курс,
// его размер зависит от числа уроков. Наведение показывает курс, клик открывает его.
(function () {
  var canvas = document.getElementById("ice-canvas");
  var dataEl = document.getElementById("hero-courses");
  if (!canvas || !dataEl || !window.THREE) return;
  var THREE = window.THREE;
  var courses = JSON.parse(dataEl.textContent || "[]");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var hero = canvas.parentElement;
  var tip = document.getElementById("ice-tip");

  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
  } catch (e) {
    return; // нет WebGL — остаётся статичный фон
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  hero.querySelector(".ice-fallback").style.opacity = "0.35";

  var scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x060a12, 9, 26);
  var camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
  camera.position.set(0, 0, 13);

  scene.add(new THREE.AmbientLight(0x7fa6c8, 0.55));
  var key = new THREE.DirectionalLight(0xe8f8ff, 1.6);
  key.position.set(4, 6, 8);
  scene.add(key);
  var rim = new THREE.PointLight(0x5fc8ff, 2.2, 30);
  rim.position.set(-6, -2, 4);
  scene.add(rim);

  function crystalGeometry(seed) {
    // вытянутый многогранник с чуть смещёнными вершинами — у каждого кристалла своя огранка
    var g = new THREE.OctahedronGeometry(1, 0);
    var pos = g.attributes.position;
    for (var i = 0; i < pos.count; i++) {
      var y = pos.getY(i);
      var k = 1 + Math.sin(seed * 12.9898 + i * 78.233) * 0.18;
      pos.setXYZ(i, pos.getX(i) * k * 0.62, y * (y > 0 ? 1.55 : 1.05), pos.getZ(i) * k * 0.62);
    }
    g.computeVertexNormals();
    return g;
  }

  var iceMat = new THREE.MeshPhysicalMaterial({
    color: 0xcdeeff,
    roughness: 0.12,
    metalness: 0.05,
    transparent: true,
    opacity: 0.62,
    emissive: new THREE.Color(0x1b4a6b),
    emissiveIntensity: 0.35,
    flatShading: true,
    clearcoat: 1,
    clearcoatRoughness: 0.1,
    side: THREE.DoubleSide,
  });
  var hoverMat = iceMat.clone();
  hoverMat.color = new THREE.Color(0xffffff);
  hoverMat.opacity = 0.85;
  hoverMat.emissive = new THREE.Color(0x2d7fb0);
  hoverMat.emissiveIntensity = 0.5;
  var edgeMat = new THREE.LineBasicMaterial({ color: 0x9fe2ff, transparent: true, opacity: 0.5 });

  var group = new THREE.Group();
  scene.add(group);
  var pickable = [];
  var maxLessons = Math.max.apply(null, courses.map(function (c) { return c.lessons || 1; }).concat([1]));

  // крупные кристаллы — курсы, раскладываем по спирали справа от заголовка
  courses.forEach(function (course, i) {
    var size = 0.55 + 0.75 * Math.sqrt((course.lessons || 1) / maxLessons);
    var geo = crystalGeometry(course.id);
    var mesh = new THREE.Mesh(geo, iceMat);
    var edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo), edgeMat);
    mesh.add(edges);
    var angle = i * 2.399; // золотой угол
    var radius = 1.4 + i * 0.52;
    mesh.position.set(4.6 + Math.cos(angle) * radius * 0.75, Math.sin(angle) * radius * 0.5 + 1.5, -i * 0.35);
    mesh.scale.setScalar(size);
    mesh.rotation.set(Math.random() * 0.6, Math.random() * Math.PI, Math.random() * 0.4);
    mesh.userData = { course: course, spin: 0.08 + Math.random() * 0.12, bob: Math.random() * Math.PI * 2, baseY: mesh.position.y };
    group.add(mesh);
    pickable.push(mesh);
  });

  // мелкие осколки для глубины
  var shardGeo = new THREE.TetrahedronGeometry(0.12, 0);
  var shardMat = new THREE.MeshBasicMaterial({ color: 0x9fd6f0, transparent: true, opacity: 0.55 });
  var shards = new THREE.InstancedMesh(shardGeo, shardMat, 140);
  var dummy = new THREE.Object3D();
  for (var s = 0; s < 140; s++) {
    dummy.position.set((Math.random() - 0.5) * 30, (Math.random() - 0.5) * 16, -Math.random() * 14 + 2);
    dummy.rotation.set(Math.random() * 6, Math.random() * 6, 0);
    dummy.scale.setScalar(0.4 + Math.random() * 1.4);
    dummy.updateMatrix();
    shards.setMatrixAt(s, dummy.matrix);
  }
  scene.add(shards);

  function resize() {
    var w = hero.clientWidth, h = hero.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // на узком экране сдвигаем поле вверх-по центру, чтобы не закрывать текст
    var narrow = w < 760;
    group.position.set(narrow ? -2.4 : 0, narrow ? 2.2 : 0, 0);
    camera.fov = narrow ? 58 : 42;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);
  resize();

  var mouse = new THREE.Vector2(-10, -10), target = { x: 0, y: 0 };
  var raycaster = new THREE.Raycaster();
  var hovered = null;

  function setHover(mesh, clientX, clientY) {
    if (hovered && hovered !== mesh) hovered.material = iceMat;
    hovered = mesh;
    if (mesh) {
      mesh.material = hoverMat;
      var c = mesh.userData.course;
      tip.innerHTML = "<b></b><span></span>";
      tip.querySelector("b").textContent = c.title;
      tip.querySelector("span").textContent = "уровней: " + c.levels + ", уроков: " + c.lessons;
      var r = hero.getBoundingClientRect();
      tip.style.left = clientX - r.left + "px";
      tip.style.top = clientY - r.top + "px";
      tip.classList.add("show");
      canvas.style.cursor = "pointer";
    } else {
      tip.classList.remove("show");
      canvas.style.cursor = "";
    }
  }

  function pick(clientX, clientY) {
    var r = canvas.getBoundingClientRect();
    mouse.x = ((clientX - r.left) / r.width) * 2 - 1;
    mouse.y = -((clientY - r.top) / r.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    var hit = raycaster.intersectObjects(pickable, false)[0];
    return hit ? hit.object : null;
  }

  hero.addEventListener("pointermove", function (e) {
    var r = hero.getBoundingClientRect();
    target.x = (e.clientX - r.left) / r.width - 0.5;
    target.y = (e.clientY - r.top) / r.height - 0.5;
    if (e.target === canvas) setHover(pick(e.clientX, e.clientY), e.clientX, e.clientY);
    else setHover(null);
    if (reduce) render();
  });
  hero.addEventListener("pointerleave", function () { setHover(null); });
  canvas.addEventListener("click", function (e) {
    var mesh = pick(e.clientX, e.clientY);
    if (!mesh) return;
    // на сенсорном экране первое касание показывает подпись, второе — открывает курс
    if (e.pointerType === "touch" || (window.matchMedia("(hover: none)").matches && hovered !== mesh)) {
      if (hovered !== mesh) { setHover(mesh, e.clientX, e.clientY); return; }
    }
    window.location.href = mesh.userData.course.url;
  });

  var visible = true;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) { visible = entries[0].isIntersecting; if (visible) loop(); }).observe(hero);
  }

  var clock = new THREE.Clock();
  function render() {
    var t = clock.getElapsedTime();
    pickable.forEach(function (m) {
      if (!reduce) {
        m.rotation.y += m.userData.spin * 0.01;
        m.position.y = m.userData.baseY + Math.sin(t * 0.6 + m.userData.bob) * 0.12;
      }
    });
    if (!reduce) shards.rotation.y = t * 0.01;
    camera.position.x += (target.x * 1.6 - camera.position.x) * 0.04;
    camera.position.y += (-target.y * 1.0 - camera.position.y) * 0.04;
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
  }
  var running = false;
  function loop() {
    if (running || reduce) return;
    running = true;
    (function frame() {
      if (!visible) { running = false; return; }
      render();
      requestAnimationFrame(frame);
    })();
  }
  render();
  loop();
})();
