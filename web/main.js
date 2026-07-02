// A Parede Invisível — experiência interativa USD/BRL × números redondos
// Terminal noturno · creative coding · Canvas 2D vanilla, scroll suave próprio
const COL = {
  bg: "#0a0e14",
  price: "#00ff9c",
  wall: "#38bdf8",
  rand: "#8b7cff",
  dim: "#4a5766",
  ink: "#e6f0f2",
  danger: "#ff4d6d",
};
const MONO = '500 12px "JetBrains Mono", monospace';

// ---------- estado global ----------
const app = { scene: "intro", p: 0, edge: 1, data: null, firedUpTo: -1, verdictFired: false };

// ---------- canvas ----------
const canvas = document.getElementById("stage");
const ctx = canvas.getContext("2d");
let W = 0, H = 0, DPR = 1;
function resize() {
  DPR = Math.min(2, window.devicePixelRatio || 1);
  // largura do conteúdo (SEM a barra de rolagem) para o canvas centralizar
  // no mesmo eixo que o texto do DOM — senão os gráficos ficam ~scrollbar/2 à direita
  W = document.documentElement.clientWidth; H = window.innerHeight;
  canvas.style.width = W + "px"; canvas.style.height = H + "px";
  canvas.width = Math.floor(W * DPR);
  canvas.height = Math.floor(H * DPR);
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
}
window.addEventListener("resize", () => { resize(); computeLayout(); });
resize();

// ---------- helpers ----------
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
const lerp = (a, b, t) => a + (b - a) * t;
const nf = (n) => Math.round(n).toLocaleString("pt-BR");
function hexA(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

// ---------- projeção do "mundo" (linha de preço) ----------
const MG = { l: 0.06, r: 0.06, t: 0.30, b: 0.24 }; // frações de W/H
let VIEW = { pLo: 0, pHi: 1, N: 1 };
function setView() {
  const d = app.data;
  const pad = (d.meta.price_max - d.meta.price_min) * 0.14;
  VIEW = { pLo: d.meta.price_min - pad, pHi: d.meta.price_max + pad, N: d.series.length };
}
const wx = (i) => W * MG.l + (i / (VIEW.N - 1)) * (W * (1 - MG.l - MG.r));
const wy = (p) => H * MG.t + (1 - (p - VIEW.pLo) / (VIEW.pHi - VIEW.pLo)) * (H * (1 - MG.t - MG.b));

// ---------- partículas (leves: sem shadowBlur, contagem limitada) ----------
const parts = [];
const MAX_PARTS = 160;
function burst(x, y, color, n, spd = 2.0) {
  if (parts.length > MAX_PARTS) return;
  for (let k = 0; k < n; k++) {
    const a = Math.random() * Math.PI * 2;
    const s = spd * (0.3 + Math.random());
    parts.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 0.4,
      life: 1, decay: 0.028 + Math.random() * 0.03, color, r: 0.7 + Math.random() * 1.1 });
  }
}
function updateParts() {
  for (let i = parts.length - 1; i >= 0; i--) {
    const p = parts[i];
    p.x += p.vx; p.y += p.vy; p.vy += 0.03; p.vx *= 0.99;
    p.life -= p.decay;
    if (p.life <= 0) parts.splice(i, 1);
  }
}
function drawParts() {
  for (const p of parts) {
    ctx.globalAlpha = clamp(p.life) * 0.85;
    ctx.fillStyle = p.color;
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 7); ctx.fill();
  }
  ctx.globalAlpha = 1;
}

// ---------- fundo ambiente ----------
function backdrop(t) {
  ctx.clearRect(0, 0, W, H);
  // grade fina
  ctx.strokeStyle = "rgba(56,189,248,0.035)"; ctx.lineWidth = 1;
  const gx = 90;
  for (let x = 0; x < W; x += gx) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = 0; y < H; y += gx) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  // scanline
  const sy = (t * 40) % (H + 120) - 60;
  const g = ctx.createLinearGradient(0, sy - 60, 0, sy + 60);
  g.addColorStop(0, "rgba(0,255,156,0)"); g.addColorStop(.5, "rgba(0,255,156,0.05)"); g.addColorStop(1, "rgba(0,255,156,0)");
  ctx.fillStyle = g; ctx.fillRect(0, sy - 60, W, 120);
}

// ---------- desenho do mundo ----------
function drawWalls(grid, alpha, dashed, labelIt) {
  const walls = app.data.walls[grid] || [];
  ctx.save();
  ctx.lineWidth = 1;
  if (dashed) ctx.setLineDash([2, 7]);
  for (const lv of walls) {
    const y = wy(lv);
    if (y < H * (MG.t - .05) || y > H * (1 - MG.b + .05)) continue;
    ctx.strokeStyle = hexA(COL.wall, alpha);
    ctx.shadowBlur = dashed ? 0 : 10; ctx.shadowColor = hexA(COL.wall, alpha * .8);
    ctx.beginPath(); ctx.moveTo(W * MG.l, y); ctx.lineTo(W * (1 - MG.r), y); ctx.stroke();
    if (labelIt) {
      ctx.shadowBlur = 0; ctx.font = MONO; ctx.fillStyle = hexA(COL.wall, alpha + .25);
      ctx.textAlign = "left"; ctx.textBaseline = "middle";
      ctx.fillText("R$ " + lv.toFixed(2).replace(".", ","), W * (1 - MG.r) + 8, y);
    }
  }
  ctx.restore();
}

function drawWorldLine(headFrac, headGlow = true) {
  const s = app.data.series;
  const head = Math.floor(clamp(headFrac) * (VIEW.N - 1));
  ctx.save();
  ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.lineWidth = 1.6;
  ctx.strokeStyle = COL.price; ctx.shadowBlur = 12; ctx.shadowColor = hexA(COL.price, .6);
  ctx.beginPath();
  for (let i = 0; i <= head; i++) {
    const x = wx(i), y = wy(s[i]);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.restore();
  if (headGlow && head > 0) {
    const x = wx(head), y = wy(s[head]);
    ctx.fillStyle = COL.price; ctx.shadowBlur = 22; ctx.shadowColor = COL.price;
    ctx.beginPath(); ctx.arc(x, y, 3.4, 0, 7); ctx.fill(); ctx.shadowBlur = 0;
  }
  return head;
}

function drawTouchDots(head, ignite) {
  const T = app.data.touches;
  ctx.save();
  ctx.globalAlpha = .5; ctx.fillStyle = hexA(COL.wall, .8);
  for (const tt of T) {
    if (tt.i > head) break;
    const x = wx(tt.i), y = wy(tt.p);
    ctx.beginPath(); ctx.arc(x, y, 1.5, 0, 7); ctx.fill();
  }
  ctx.globalAlpha = 1;
  ctx.restore();
  // acende faíscas leves só nos toques recém-cruzados
  if (ignite) {
    if (head < app.firedUpTo) app.firedUpTo = head;
    let spawned = 0;
    for (const tt of T) {
      if (tt.i <= app.firedUpTo) continue;
      if (tt.i > head) break;
      if (spawned < 4) { burst(wx(tt.i), wy(tt.p), COL.wall, 3, 1.4); spawned++; }
    }
    app.firedUpTo = head;
  }
}

// ---------- DOM refs ----------
const el = (s) => document.querySelector(s);
const beats = [...document.querySelectorAll(".beat")];
const ui = {
  ctMin: el("#ct-min"), ctTouch: el("#ct-touch"), ctDays: el("#ct-days"),
  counters: el(".counters"),
  versus: el(".versus"), vsRound: el("#vs-round"), vsRand: el("#vs-rand"),
  expVerdict: el("#exp-verdict"),
  legend: el("#es-legend"),
  coda: el(".coda"),
  sceneLabel: el("#scene-label"),
  hint: el("#scroll-hint"),
};
function fade(node, v) { if (node) node.style.opacity = v; }

// ---------- cenas ----------
function sceneIntro(t) {
  const auto = clamp((t - 0.4) / 2.6);         // auto-desenha ao carregar
  const rev = Math.max(auto, smooth(app.p));   // e continua com scroll
  ctx.save();
  ctx.globalAlpha = 0.3;                        // recuado: deixa o título verde respirar
  drawWalls("0.10", 0.05 + app.p * 0.05, false, false);
  drawWorldLine(rev, false);
  ctx.restore();
}

function sceneBelief(t) {
  // ilustração calma da CRENÇA, confinada à DIREITA (o texto ocupa a esquerda):
  // uma bolinha sobe devagar, toca a parede e ricocheteia. Sutil, não protagonista.
  const x0 = W * 0.55, x1 = W * 0.95, span = x1 - x0;
  const wallY = H * 0.40;
  const w = 0.5;                                  // devagar
  ctx.save();
  ctx.globalAlpha = 0.6;                          // recuada, não rouba a atenção
  // paredes-fantasma: a crença vale para TODO número redondo
  ctx.strokeStyle = hexA(COL.wall, .10); ctx.lineWidth = 1; ctx.setLineDash([2, 9]);
  for (const gy of [-0.15, 0.15, 0.29]) {
    const y = wallY + H * gy;
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
  }
  ctx.setLineDash([]);
  // parede em foco
  ctx.strokeStyle = hexA(COL.wall, .4); ctx.lineWidth = 1.4;
  ctx.beginPath(); ctx.moveTo(x0, wallY); ctx.lineTo(x1, wallY); ctx.stroke();
  ctx.font = MONO; ctx.fillStyle = hexA(COL.wall, .6);
  ctx.textAlign = "right"; ctx.textBaseline = "bottom";
  ctx.fillText("todo número redondo", x1, wallY - 8);
  // trajetória idealizada e lenta: sobe, toca, ricocheteia
  const amp = H * 0.1, nS = 180;
  ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.lineWidth = 1.4;
  ctx.strokeStyle = hexA(COL.price, .85);
  ctx.beginPath();
  let hx = 0, hy = 0;
  for (let k = 0; k <= nS; k++) {
    const u = k / nS;
    const phase = (u * 5) - t * w;
    const d = amp * Math.abs(Math.sin(phase));   // distância abaixo da parede
    const x = x0 + u * span, y = wallY + d;
    if (k === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    hx = x; hy = y;
  }
  ctx.stroke();
  ctx.fillStyle = COL.price;
  ctx.beginPath(); ctx.arc(hx, hy, 3, 0, 7); ctx.fill();
  ctx.restore();

  // flash discreto de "toque" quando encosta
  const tp = Math.abs(Math.sin(5 - t * w));
  if (tp < 0.03) burst(hx, wallY, COL.wall, 2, 1.0);
}

function sceneData() {
  drawWalls("0.10", 0.12, false, true);
  const rev = smooth(clamp((app.p - 0.04) / 0.82));
  const head = drawWorldLine(rev);
  drawTouchDots(head, true);
  // counters
  fade(ui.counters, (app.p > 0.06 ? 1 : 0) * app.edge);
  const c = app.data;
  ui.ctMin.textContent = nf(rev * c.meta.n_minutes);
  ui.ctDays.textContent = nf(rev * c.meta.n_days);
  const nT = c.touches.filter((x) => x.i <= head).length;
  ui.ctTouch.textContent = nf(nT);
}

function sceneExperiment() {
  // fundo: paredes redondas sólidas vs níveis sorteados (fantasma, tracejado)
  drawWalls("0.50", 0.16, false, false);
  ctx.save();
  ctx.setLineDash([2, 8]); ctx.strokeStyle = hexA(COL.rand, .18); ctx.lineWidth = 1;
  const ghosts = [0.62, 0.31, 0.78, 0.44, 0.55];
  for (const gg of ghosts) { const y = H * (0.30 + gg * 0.42); ctx.beginPath(); ctx.moveTo(W * 0.06, y); ctx.lineTo(W * 0.94, y); ctx.stroke(); }
  ctx.restore();

  const h = app.data.headline;
  const rnd = app.data.experiment.find((e) => e.grade === h.grade && !e.placebo);
  const k = smooth(clamp((app.p - 0.1) / 0.6));
  fade(ui.versus, (app.p > 0.08 ? 1 : 0) * app.edge);
  ui.vsRound.textContent = (k * h.redondo).toFixed(1).replace(".", ",") + "%";
  ui.vsRand.textContent = (k * h.sorteado).toFixed(1).replace(".", ",") + "%";
  fade(ui.expVerdict, (app.p > 0.72 ? 1 : 0) * app.edge);
}

// event-study (ricochete)
const ES = [
  { key: "Controle (Osler)", col: COL.dim, band: false, lw: 1.6 },
  { key: "R$0,50", col: COL.wall, band: true, lw: 2 },
  { key: "R$1,00", col: COL.price, band: true, lw: 2 },
];
function sceneRicochet() {
  const es = app.data.event_study;
  const x0 = W * 0.16, x1 = W * 0.84, y0 = H * 0.50, y1 = H * 0.85;
  const kMin = -10, kMax = 30, vMin = -8, vMax = 3;
  const px = (k) => x0 + ((k - kMin) / (kMax - kMin)) * (x1 - x0);
  const py = (v) => y1 - ((v - vMin) / (vMax - vMin)) * (y1 - y0);
  const rev = smooth(clamp((app.p - 0.08) / 0.72));
  const kNow = kMin + rev * (kMax - kMin);

  // eixo zero
  ctx.save();
  ctx.setLineDash([3, 6]); ctx.strokeStyle = hexA(COL.ink, .18); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x0, py(0)); ctx.lineTo(x1, py(0)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.font = MONO; ctx.fillStyle = hexA(COL.dim, .9); ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.fillText("0 bps", x1 + 8, py(0));
  // marcador do toque k=0 (rótulo embaixo, longe do título)
  ctx.strokeStyle = hexA(COL.danger, .5); ctx.beginPath(); ctx.moveTo(px(0), y0 - 6); ctx.lineTo(px(0), y1 + 6); ctx.stroke();
  // rótulos de eixo x
  ctx.fillStyle = hexA(COL.dim, .7); ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (const kk of [-10, 10, 20, 30]) ctx.fillText((kk > 0 ? "+" : "") + kk + " min", px(kk), y1 + 12);
  ctx.fillStyle = hexA(COL.danger, .95);
  ctx.fillText("toque (k=0)", px(0), y1 + 12);
  ctx.restore();

  // bandas ±se + linhas
  for (const g of ES) {
    const d = es[g.key]; if (!d) continue;
    const K = d.k, M = d.mean, S = d.se;
    if (g.band) {
      ctx.fillStyle = hexA(g.col, .10);
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < K.length; i++) { if (K[i] > kNow) break; const x = px(K[i]), y = py(M[i] + S[i]); if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y); }
      for (let i = K.length - 1; i >= 0; i--) { if (K[i] > kNow) continue; ctx.lineTo(px(K[i]), py(M[i] - S[i])); }
      if (started) { ctx.closePath(); ctx.fill(); }
    }
  }
  for (const g of ES) {
    const d = es[g.key]; if (!d) continue;
    const K = d.k, M = d.mean;
    ctx.strokeStyle = g.col; ctx.lineWidth = g.lw; ctx.lineJoin = "round"; ctx.lineCap = "round";
    ctx.shadowBlur = g.band ? 8 : 0; ctx.shadowColor = hexA(g.col, .5);
    ctx.beginPath(); let started = false;
    for (let i = 0; i < K.length; i++) {
      if (K[i] > kNow) {
        // segmento parcial
        if (i > 0 && K[i - 1] <= kNow) {
          const tt = (kNow - K[i - 1]) / (K[i] - K[i - 1]);
          ctx.lineTo(px(kNow), py(lerp(M[i - 1], M[i], tt)));
        }
        break;
      }
      const x = px(K[i]), y = py(M[i]);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke(); ctx.shadowBlur = 0;
  }
  fade(ui.legend, (rev > 0.12 ? 1 : 0) * app.edge);
}

function sceneVerdict() {
  // dispara o estilhaçamento das paredes ao entrar
  if (!app.verdictFired) {
    const walls = app.data.walls["0.50"];
    for (const lv of walls) {
      const y = wy(lv);
      for (let x = W * 0.10; x < W * 0.90; x += 64) burst(x, y, COL.wall, 2, 2.6);
    }
    app.verdictFired = true;
  }
  // a linha atravessa reto — recuada, para o título verde ficar legível por cima
  ctx.save();
  ctx.globalAlpha = 0.28;
  drawWorldLine(1, false);
  ctx.restore();
  fade(ui.coda, (app.p > 0.3 ? 1 : 0) * app.edge);
}

// ---------- layout + scroll suave (sem ScrollTrigger: controlamos tudo por frame) ----------
let layout = [];
function computeLayout() {
  layout = beats.map((b) => ({
    el: b, scene: b.dataset.scene, label: b.dataset.label,
    copy: b.querySelector(".copy"),
    start: b.offsetTop,
    len: Math.max(1, b.offsetHeight),
  }));
}
// opacidade por beat: sem sobreposição — cada capítulo (texto + gráfico) some por
// completo no "respiro" escuro antes do próximo surgir. Também governa app.edge (palco).
function beatOpacity(prog, idx) {
  const w = 0.14;                                   // largura do fade em cada ponta
  const lo = idx === 0 ? 1 : prog / w;              // surge do vazio
  const hi = idx === layout.length - 1 ? 1 : (1 - prog) / w; // volta ao vazio
  return smooth(clamp(Math.min(lo, hi)));
}

let smoothY = 0, prevScene = "";
function updateScroll() {
  const targetY = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
  smoothY += (targetY - smoothY) * 0.13;           // inércia cinematográfica
  if (Math.abs(targetY - smoothY) < 0.4) smoothY = targetY;
  if (!layout.length) return;

  let active = layout[0], prog = 0, aIdx = 0;
  for (let i = 0; i < layout.length; i++) {
    const L = layout[i];
    const p = (smoothY - L.start) / L.len;
    L.copy.style.opacity = beatOpacity(p, i);
    if (smoothY >= L.start - 0.5) { active = L; prog = p; aIdx = i; }
  }
  app.scene = active.scene;
  app.p = clamp(prog);
  app.edge = beatOpacity(prog, aIdx);

  if (active.scene !== prevScene) {
    parts.length = 0;                              // limpa faíscas ao trocar de cena
    if (prevScene === "data") app.firedUpTo = -1;
    if (active.scene !== "verdict") app.verdictFired = false;
    ui.sceneLabel.textContent = active.label;
    document.querySelectorAll("#rail button").forEach((b) => b.classList.toggle("on", b.dataset.scene === active.scene));
    prevScene = active.scene;
  }
  fade(ui.hint, active.scene === "intro" ? app.edge : 0);
}

// ---------- loop ----------
let start = performance.now();
function frame(now) {
  const t = (now - start) / 1000;
  if ((W === 0 || H === 0) && window.innerWidth > 0) { resize(); computeLayout(); }
  updateScroll();
  backdrop(t);
  switch (app.scene) {
    case "intro": sceneIntro(t); break;
    case "belief": sceneBelief(t); break;
    case "data": sceneData(); break;
    case "experiment": sceneExperiment(); break;
    case "ricochet": sceneRicochet(); break;
    case "verdict": sceneVerdict(); break;
  }
  updateParts(); drawParts();
  // respiro entre capítulos: escurece o palco na virada, suavizando a troca de cena
  if (app.edge < 0.999) {
    ctx.globalAlpha = clamp(1 - app.edge);
    ctx.fillStyle = COL.bg; ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = 1;
  }
  requestAnimationFrame(frame);
}

// ---------- rail ----------
function buildRail() {
  const rail = document.getElementById("rail");
  beats.forEach((b) => {
    const btn = document.createElement("button");
    btn.dataset.scene = b.dataset.scene;
    btn.innerHTML = `<span class="rl-txt">${b.dataset.label}</span><span class="tick"></span>`;
    btn.addEventListener("click", () => window.scrollTo({ top: b.offsetTop + 4, behavior: "smooth" }));
    rail.appendChild(btn);
  });
}

// ---------- boot ----------
(async function boot() {
  const res = await fetch("data.json");
  app.data = await res.json();
  setView();
  const cr = document.getElementById("coda-range");
  if (cr) cr.textContent = `${app.data.meta.date_start} → ${app.data.meta.date_end}`;
  buildRail();
  computeLayout();
  // deep-link opcional: ?goto=<cena> pula para o capítulo (útil para revisão)
  const goto = new URLSearchParams(location.search).get("goto");
  if (goto) {
    const L = layout.find((l) => l.scene === goto);
    if (L) { const y = L.start + L.len * 0.5; window.scrollTo(0, y); smoothY = y; }
  } else {
    smoothY = window.scrollY || 0;
  }
  requestAnimationFrame(frame);
})();
