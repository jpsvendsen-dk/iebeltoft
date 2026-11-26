'use strict';
(() => {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context) return;
  canvas.className = 'cursor-snow';
  canvas.setAttribute('aria-hidden', 'true');
  document.body.append(canvas);
  let flakes = [], frame = 0, previous = 0, lastSpawn = -Infinity;
  function clear() {
    cancelAnimationFrame(frame); frame = 0; previous = 0; flakes = [];
    context.clearRect(0, 0, innerWidth, innerHeight);
  }
  function resize() {
    clear();
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(innerWidth * ratio);
    canvas.height = Math.round(innerHeight * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
  }
  function draw(now) {
    const elapsed = previous ? Math.min((now - previous) / 1000, .05) : 0;
    previous = now;
    context.clearRect(0, 0, innerWidth, innerHeight);
    for (const flake of flakes) {
      flake.age += elapsed;
      flake.x += flake.drift * elapsed;
      flake.y += flake.fall * elapsed;
      context.globalAlpha = .8 * Math.max(0, 1 - flake.age / flake.life);
      context.beginPath();
      context.arc(flake.x + Math.sin(flake.age * 4 + flake.phase) * 5, flake.y, flake.size, 0, Math.PI * 2);
      context.fillStyle = '#fff9ed';
      context.fill();
    }
    context.globalAlpha = 1;
    flakes = flakes.filter(flake => flake.age < flake.life);
    if (flakes.length) frame = requestAnimationFrame(draw);
    else { frame = 0; previous = 0; }
  }
  document.addEventListener('pointermove', event => {
    if (event.pointerType !== 'mouse' || reduced.matches || document.hidden || document.querySelector('dialog[open]')) return;
    const now = performance.now();
    if (now - lastSpawn < 28) return;
    lastSpawn = now;
    for (let i = 0; i < 2; i++) {
      flakes.push({x:event.clientX + (Math.random() - .5) * 10, y:event.clientY + 5, age:0, life:.9 + Math.random() * .6, size:1.3 + Math.random() * 1.8, drift:(Math.random() - .5) * 25, fall:32 + Math.random() * 35, phase:Math.random() * Math.PI * 2});
    }
    if (flakes.length > 64) flakes.splice(0, flakes.length - 64);
    if (!frame) frame = requestAnimationFrame(draw);
  }, {passive:true});
  window.addEventListener('resize', resize);
  window.addEventListener('blur', clear);
  document.addEventListener('visibilitychange', clear);
  reduced.addEventListener('change', clear);
  resize();
})();
