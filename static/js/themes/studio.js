// «Студия»: жидкий фон на WebGL. Наведение на курс в списке перекрашивает фон в цвет курса,
// рядом с курсором появляется его обложка.
(function () {
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canvas = document.getElementById("studio-canvas");

  function hsl(h, s, l) {
    h = ((h % 360) + 360) % 360 / 360;
    function f(n) {
      var k = (n + h * 12) % 12, a = s * Math.min(l, 1 - l);
      return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    }
    return [f(0), f(8), f(4)];
  }

  var base = hsl(14, 0.95, 0.55); // тёплый оранжевый по умолчанию
  var color = base.slice(), target = base.slice();
  var mouse = [0.7, 0.4], mouseT = [0.7, 0.4];

  // ---------- шоурил: цвет и превью ----------
  var preview = document.getElementById("reel-preview");
  document.querySelectorAll("#reel a").forEach(function (a) {
    var hue = parseInt(a.dataset.hue || "0", 10);
    function on() {
      target = hsl(hue, 0.9, 0.55);
      var tpl = a.querySelector("template");
      if (preview && tpl) { preview.innerHTML = tpl.innerHTML; preview.classList.add("show"); }
    }
    function off() { target = base.slice(); if (preview) preview.classList.remove("show"); }
    a.addEventListener("pointerenter", on);
    a.addEventListener("focus", on);
    a.addEventListener("pointerleave", off);
    a.addEventListener("blur", off);
  });
  window.addEventListener("pointermove", function (e) {
    mouseT = [e.clientX / window.innerWidth, 1 - e.clientY / window.innerHeight];
    if (preview) {
      var x = Math.min(e.clientX + 260, window.innerWidth - 170);
      preview.style.left = x + "px";
      preview.style.top = e.clientY + "px";
    }
  });

  if (!canvas) return;
  var gl = canvas.getContext("webgl", { antialias: false, premultipliedAlpha: false });
  if (!gl) return;
  canvas.parentElement.querySelector(".fallback").style.display = "none";

  var vs = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
  var fs = [
    "precision mediump float;",
    "uniform vec2 r;uniform float t;uniform vec3 c;uniform vec2 m;",
    "float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}",
    "float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);",
    " return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}",
    "float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*n(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}",
    "void main(){",
    " vec2 uv=gl_FragCoord.xy/r.xy; vec2 p=uv*vec2(r.x/r.y,1.)*1.6;",
    " vec2 q=vec2(fbm(p+t*.05),fbm(p+vec2(5.2,1.3)-t*.04));",
    " vec2 w=vec2(fbm(p+3.*q+vec2(1.7,9.2)+t*.06),fbm(p+3.*q+vec2(8.3,2.8)));",
    " float f=fbm(p+3.5*w);",
    " float d=distance(uv,m); float glow=smoothstep(.65,0.,d);",
    " vec3 col=mix(vec3(0.),c,smoothstep(.35,.95,f)*(.55+.6*glow));",
    " col+=c*pow(f,6.)*1.2; col*=smoothstep(1.25,.2,length(uv-vec2(.62,.55)));",
    " gl_FragColor=vec4(col,1.);",
    "}",
  ].join("\n");

  function sh(type, src) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return s;
  }
  var prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, vs));
  gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { canvas.parentElement.querySelector(".fallback").style.display = ""; return; }
  gl.useProgram(prog);
  var buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  var loc = gl.getAttribLocation(prog, "p");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  var uR = gl.getUniformLocation(prog, "r"), uT = gl.getUniformLocation(prog, "t");
  var uC = gl.getUniformLocation(prog, "c"), uM = gl.getUniformLocation(prog, "m");

  var scale = 0.5; // считаем в половинном разрешении — жидкость мягкая, а видеокарте легче
  function resize() {
    canvas.width = Math.round(window.innerWidth * scale);
    canvas.height = Math.round(window.innerHeight * scale);
    gl.viewport(0, 0, canvas.width, canvas.height);
  }
  window.addEventListener("resize", resize);
  resize();

  var t0 = performance.now();
  function frame(now) {
    for (var i = 0; i < 3; i++) color[i] += (target[i] - color[i]) * 0.04;
    mouse[0] += (mouseT[0] - mouse[0]) * 0.05;
    mouse[1] += (mouseT[1] - mouse[1]) * 0.05;
    gl.uniform2f(uR, canvas.width, canvas.height);
    gl.uniform1f(uT, reduce ? 12.0 : (now - t0) / 1000);
    gl.uniform3f(uC, color[0], color[1], color[2]);
    gl.uniform2f(uM, mouse[0], mouse[1]);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    if (!document.hidden) requestAnimationFrame(frame);
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) requestAnimationFrame(frame); });
  requestAnimationFrame(frame);
})();
