// ===========================================================================
// FaceHunt-2 — frontend
// ===========================================================================
const TOKEN = new URLSearchParams(location.search).get("token") || "";

// --------------------------------------------------------------------------
// i18n
// --------------------------------------------------------------------------
const I18N = {
  es: {
    "app.tagline": "Encontrá a una persona en cualquier video",
    "nav.repo": "Repositorio",
    "nav.contact": "Contacto",
    "step.reference": "Referencia", "step.video": "Video",
    "step.options": "Opciones", "step.results": "Resultados",
    "ref.title": "Subí la foto de referencia",
    "ref.hint": "Una o varias fotos frontales y nítidas de la misma persona. Varias fotos mejoran la precisión.",
    "ref.drop.strong": "Arrastrá imágenes",
    "common.drop.rest": "o hacé clic para elegir",
    "ref.validate": "Validar referencia",
    "vid.title": "Elegí el video",
    "vid.tab.file": "Archivo local", "vid.tab.url": "URL de YouTube",
    "vid.drop.strong": "Arrastrá un video",
    "vid.url.paste": "Tip: clic derecho para pegar del portapapeles.",
    "vid.validate": "Validar video",
    "opt.title": "Elegí cómo buscar",
    "opt.balanced.name": "Rápido",
    "opt.balanced.desc": "Analiza 2 cuadros por segundo. Suficiente para la mayoría.",
    "opt.precision.name": "Exhaustivo",
    "opt.precision.desc": "Analiza 5 cuadros por segundo y busca caras más chicas. Encuentra más, tarda más.",
    "opt.start": "Iniciar búsqueda",
    "common.back": "Atrás", "common.cancel": "Cancelar",
    "common.validating": "Validando…",
    "proc.analyzing": "Analizando…",
    "proc.title.download": "Descargando video…",
    "proc.title.analyze": "Analizando video…",
    "res.new": "Nueva búsqueda",
    "res.none": "No se encontraron apariciones de esa persona.",
    "err.title": "Algo salió mal", "err.retry": "Reintentar",
    "foot.text": "FaceHunt2 · 100% local · tus fotos y videos no salen de tu equipo",
    "err.connect": "Error al conectar con el servidor.",
    "err.cancelled": "Búsqueda cancelada.",
    "alert.image": "Validá primero la imagen de referencia (Paso 1).",
    "alert.video": "Validá primero el video (Paso 2).",
    "toast.repo": "Repositorio: próximamente.",
    "contact.eyebrow": "Contacto",
    "contact.open": "Abrir en tu app de correo",
    "phrases": ["Buscando rostros…", "Comparando caras…", "Revisando cuadro por cuadro…", "Afinando coincidencias…", "Casi listo…"],
    "fn.count": (p, t, m) => `${p}/${t || "?"} cuadros · ${m} coincidencias`,
    "fn.eta": (mm, ss) => `~${mm}:${ss} restante`,
    "fn.found": (n) => `${n} aparición${n === 1 ? "" : "es"} encontrada${n === 1 ? "" : "s"}`,
    "fn.frames": (n) => `${n} cuadro${n === 1 ? "" : "s"}`,
  },
  en: {
    "app.tagline": "Find a person in any video",
    "nav.repo": "Repository",
    "nav.contact": "Contact",
    "step.reference": "Reference", "step.video": "Video",
    "step.options": "Options", "step.results": "Results",
    "ref.title": "Upload the reference photo",
    "ref.hint": "One or more clear, front-facing photos of the same person. More photos improve accuracy.",
    "ref.drop.strong": "Drag images",
    "common.drop.rest": "or click to choose",
    "ref.validate": "Validate reference",
    "vid.title": "Choose the video",
    "vid.tab.file": "Local file", "vid.tab.url": "YouTube URL",
    "vid.drop.strong": "Drag a video",
    "vid.url.paste": "Tip: right-click to paste from the clipboard.",
    "vid.validate": "Validate video",
    "opt.title": "Choose how to search",
    "opt.balanced.name": "Fast",
    "opt.balanced.desc": "Scans 2 frames per second. Enough for most cases.",
    "opt.precision.name": "Thorough",
    "opt.precision.desc": "Scans 5 frames per second and looks for smaller faces. Finds more, takes longer.",
    "opt.start": "Start search",
    "common.back": "Back", "common.cancel": "Cancel",
    "common.validating": "Validating…",
    "proc.analyzing": "Analyzing…",
    "proc.title.download": "Downloading video…",
    "proc.title.analyze": "Analyzing video…",
    "res.new": "New search",
    "res.none": "No appearances of that person were found.",
    "err.title": "Something went wrong", "err.retry": "Retry",
    "foot.text": "FaceHunt2 · 100% local · your photos and videos never leave your device",
    "err.connect": "Could not connect to the server.",
    "err.cancelled": "Search cancelled.",
    "alert.image": "Validate the reference image first (Step 1).",
    "alert.video": "Validate the video first (Step 2).",
    "toast.repo": "Repository: coming soon.",
    "contact.eyebrow": "Contact",
    "contact.open": "Open in your mail app",
    "phrases": ["Looking for faces…", "Comparing faces…", "Scanning frame by frame…", "Refining matches…", "Almost there…"],
    "fn.count": (p, t, m) => `${p}/${t || "?"} frames · ${m} matches`,
    "fn.eta": (mm, ss) => `~${mm}:${ss} remaining`,
    "fn.found": (n) => `${n} appearance${n === 1 ? "" : "s"} found`,
    "fn.frames": (n) => `${n} frame${n === 1 ? "" : "s"}`,
  },
};

let lang = localStorage.getItem("fh2lang") || "es";
const t = (key) => (I18N[lang] && I18N[lang][key]) ?? I18N.es[key] ?? key;

function applyI18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const v = t(el.dataset.i18n);
    if (typeof v === "string") el.textContent = v;
  });
  $$("#langSwitch button").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
  if (state.lastStatus && !results.classList.contains("hidden")) renderResults(state.lastStatus);
}

// --------------------------------------------------------------------------
const state = {
  refFiles: [], referenceId: null,
  videoType: "file", videoFile: null, videoToken: null, videoUrl: null, videoKind: null,
  jobId: null, events: null, ranges: [], localUrl: null, startedAt: 0,
  lastStatus: null, phraseTimer: null,
};

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

async function api(path, { method = "GET", body = null, json = null } = {}) {
  const headers = { "X-Auth-Token": TOKEN };
  if (json) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  const res = await fetch(path, { method, headers, body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const msg = typeof detail === "string" ? detail : detail?.message || "Error";
    throw new Error(msg);
  }
  return data;
}

function goStep(n) {
  $$(".panel").forEach((p) => p.classList.toggle("active", +p.dataset.panel === n));
  $$("#stepper li").forEach((li) => {
    const s = +li.dataset.step;
    li.classList.toggle("active", s === n);
    li.classList.toggle("done", s < n);
  });
}
function showMsg(el, text, type = "info") { el.textContent = text; el.className = `msg ${type}`; el.classList.remove("hidden"); }
function hideMsg(el) { el.classList.add("hidden"); }

let toastTimer;
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden"); requestAnimationFrame(() => el.classList.add("show"));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.classList.add("hidden"), 250); }, 2600);
}

// ===========================================================================
// Idioma + nav
// ===========================================================================
$$("#langSwitch button").forEach((b) =>
  b.addEventListener("click", () => {
    if (b.dataset.lang === lang) return;
    lang = b.dataset.lang;
    localStorage.setItem("fh2lang", lang);
    applyI18n();
  })
);
$("#repoBtn").addEventListener("click", () => toast(t("toast.repo")));

// --- Modal de contacto ---
const contactModal = $("#contactModal");
const copyEmailBtn = $("#copyEmailBtn");
function openContact() { contactModal.classList.remove("hidden"); copyEmailBtn.focus(); }
function closeContact() {
  contactModal.classList.add("hidden");
  copyEmailBtn.classList.remove("copied");
}
$("#contactBtn").addEventListener("click", openContact);
$("#contactClose").addEventListener("click", closeContact);
contactModal.addEventListener("mousedown", (e) => { if (e.target === contactModal) closeContact(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !contactModal.classList.contains("hidden")) closeContact(); });
copyEmailBtn.addEventListener("click", async () => {
  const email = $("#contactEmail").textContent.trim();
  try {
    await navigator.clipboard.writeText(email);
    copyEmailBtn.classList.add("copied");
    setTimeout(() => { copyEmailBtn.classList.remove("copied"); }, 1800);
  } catch {
    /* sin acceso al portapapeles: el email es seleccionable con user-select:all */
  }
});

// ===========================================================================
// PASO 1 — Referencia
// ===========================================================================
const imgDrop = $("#imgDrop"), imgInput = $("#imgInput"), imgPreviews = $("#imgPreviews");
const imgMsg = $("#imgMsg"), validateImgBtn = $("#validateImgBtn");

imgDrop.addEventListener("click", () => imgInput.click());
["dragover", "dragleave", "drop"].forEach((ev) =>
  imgDrop.addEventListener(ev, (e) => {
    e.preventDefault();
    imgDrop.classList.toggle("drag", ev === "dragover");
    if (ev === "drop") addImages([...e.dataTransfer.files]);
  })
);
imgInput.addEventListener("change", (e) => {
  addImages([...e.target.files]);
  e.target.value = ""; // permite re-seleccionar el mismo archivo tras borrarlo
});

function addImages(files) {
  files.filter((f) => f.type.startsWith("image/")).forEach((f) => state.refFiles.push(f));
  state.referenceId = null;  // el set cambió: hay que re-validar antes de buscar
  renderPreviews();
}
function renderPreviews() {
  imgPreviews.innerHTML = "";
  state.refFiles.forEach((f, i) => {
    const div = document.createElement("div");
    div.className = "thumb";
    const img = document.createElement("img");
    img.src = URL.createObjectURL(f);
    const btn = document.createElement("button");
    btn.textContent = "×";
    btn.onclick = (e) => { e.stopPropagation(); state.refFiles.splice(i, 1); state.referenceId = null; renderPreviews(); };
    div.append(img, btn);
    imgPreviews.appendChild(div);
  });
  imgPreviews.classList.toggle("hidden", state.refFiles.length === 0);
  validateImgBtn.disabled = state.refFiles.length === 0;
}

validateImgBtn.addEventListener("click", async () => {
  validateImgBtn.disabled = true;
  validateImgBtn.textContent = t("common.validating");
  hideMsg(imgMsg);
  try {
    const fd = new FormData();
    state.refFiles.forEach((f) => fd.append("files", f));
    const data = await api("/api/reference", { method: "POST", body: fd });
    state.referenceId = data.reference_id;
    showMsg(imgMsg, data.message, data.multiple_faces_warning ? "warn" : "success");
    setTimeout(() => goStep(2), 700);
  } catch (err) {
    showMsg(imgMsg, err.message, "error");
  } finally {
    validateImgBtn.disabled = false;
    validateImgBtn.textContent = t("ref.validate");
  }
});

// ===========================================================================
// PASO 2 — Video
// ===========================================================================
const vidDrop = $("#vidDrop"), vidInput = $("#vidInput"), vidName = $("#vidName");
const urlInput = $("#urlInput"), vidMsg = $("#vidMsg"), validateVidBtn = $("#validateVidBtn");

$$("#videoTabs .tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    $$("#videoTabs .tab").forEach((x) => x.classList.remove("active"));
    tab.classList.add("active");
    state.videoType = tab.dataset.tab;
    $$(".tab-body").forEach((b) => b.classList.toggle("hidden", b.dataset.tabbody !== state.videoType));
    hideMsg(vidMsg);
    refreshVidBtn();
  })
);
vidDrop.addEventListener("click", () => vidInput.click());
["dragover", "dragleave", "drop"].forEach((ev) =>
  vidDrop.addEventListener(ev, (e) => {
    e.preventDefault();
    vidDrop.classList.toggle("drag", ev === "dragover");
    if (ev === "drop" && e.dataTransfer.files[0]) setVideoFile(e.dataTransfer.files[0]);
  })
);
vidInput.addEventListener("change", (e) => e.target.files[0] && setVideoFile(e.target.files[0]));

function setVideoFile(f) {
  state.videoFile = f; state.videoToken = null;
  vidName.innerHTML = `<span>🎬 ${f.name}</span><span>${(f.size / 1048576).toFixed(1)} MB</span>`;
  vidName.classList.remove("hidden");
  refreshVidBtn();
}
urlInput.addEventListener("input", () => { state.videoToken = null; refreshVidBtn(); });

// Clic derecho en la URL = pegar del portapapeles (estilo terminal de Windows).
urlInput.addEventListener("contextmenu", async (e) => {
  e.preventDefault();
  try {
    const text = await navigator.clipboard.readText();
    if (text) { urlInput.value = text.trim(); urlInput.dispatchEvent(new Event("input")); }
  } catch { /* sin permiso de portapapeles: no hacemos nada */ }
});

function refreshVidBtn() {
  validateVidBtn.disabled = state.videoType === "file" ? !state.videoFile : !urlInput.value.trim();
}

validateVidBtn.addEventListener("click", async () => {
  validateVidBtn.disabled = true;
  validateVidBtn.textContent = t("common.validating");
  hideMsg(vidMsg);
  try {
    const fd = new FormData();
    if (state.videoType === "file") fd.append("file", state.videoFile);
    else fd.append("source", urlInput.value.trim());
    const data = await api("/api/video/validate", { method: "POST", body: fd });
    state.videoKind = data.kind;
    if (state.videoType === "file") state.videoToken = data.video_token;
    else state.videoUrl = urlInput.value.trim();
    showMsg(vidMsg, data.message, "success");
    setTimeout(() => goStep(3), 700);
  } catch (err) {
    showMsg(vidMsg, err.message, "error");
  } finally {
    validateVidBtn.disabled = false;
    validateVidBtn.textContent = t("vid.validate");
  }
});
$("#backTo1").addEventListener("click", () => goStep(1));

// ===========================================================================
// PASO 3 — Opciones
// ===========================================================================
const selectedMode = () => document.querySelector('input[name="mode"]:checked').value;

$$('input[name="mode"]').forEach((radio) =>
  radio.addEventListener("change", (e) =>
    $$(".mode").forEach((m) => m.classList.toggle("active", m.contains(e.target)))
  )
);
$("#backTo2").addEventListener("click", () => goStep(2));
$("#startBtn").addEventListener("click", startSearch);

// ===========================================================================
// PASO 4 — Procesamiento + resultados
// ===========================================================================
const processing = $("#processing"), results = $("#results"), errorBox = $("#errorBox");
const progFill = $("#progFill"), progPct = $("#progPct"), progCount = $("#progCount"), progEta = $("#progEta");
const procMsg = $("#procMsg"), procTitle = $("#procTitle"), procPhrase = $("#procPhrase");

function startPhrases() {
  let i = 0;
  const tick = () => {
    const phrases = t("phrases");
    procPhrase.style.opacity = 0;
    setTimeout(() => { procPhrase.textContent = phrases[i % phrases.length]; procPhrase.style.opacity = 1; i++; }, 250);
  };
  tick();
  state.phraseTimer = setInterval(tick, 2600);
}
function stopPhrases() { clearInterval(state.phraseTimer); state.phraseTimer = null; procPhrase.textContent = ""; }

async function startSearch() {
  if (!state.referenceId) { toast(t("alert.image")); return goStep(1); }
  if (!state.videoToken && !state.videoUrl) { toast(t("alert.video")); return goStep(2); }

  goStep(4);
  processing.classList.remove("hidden");
  results.classList.add("hidden");
  errorBox.classList.add("hidden");
  setProgress(0); progCount.textContent = ""; progEta.textContent = "";
  procTitle.textContent = t("proc.analyzing");
  state.startedAt = Date.now();
  startPhrases();

  try {
    const body = { reference_id: state.referenceId, mode: selectedMode() };
    if (state.videoKind === "youtube") body.video_url = state.videoUrl;
    else body.video_token = state.videoToken;
    const { job_id } = await api("/api/jobs", { method: "POST", json: body });
    state.jobId = job_id;
    listen(job_id);
  } catch (err) { showError(err.message); }
}

function listen(jobId) {
  if (state.events) state.events.close();
  const es = new EventSource(`/api/jobs/${jobId}/events?token=${encodeURIComponent(TOKEN)}`);
  state.events = es;
  es.onmessage = (e) => {
    const s = JSON.parse(e.data);
    if (s.status === "downloading") {
      procTitle.textContent = t("proc.title.download");
      setProgress(s.progress); procMsg.textContent = s.message;
    } else if (s.status === "processing") {
      procTitle.textContent = t("proc.title.analyze");
      setProgress(s.progress);
      progCount.textContent = t("fn.count")(s.processed, s.total, s.matches);
      progEta.textContent = eta(s.progress);
      procMsg.textContent = "";
    } else if (s.status === "done") { es.close(); showResults(s); }
    else if (s.status === "cancelled") { es.close(); showError(t("err.cancelled")); }
    else if (s.status === "error") { es.close(); showError(s.message); }
  };
  es.onerror = () => { es.close(); pollOnce(jobId); };
}

async function pollOnce(jobId, failures = 0) {
  try {
    const s = await api(`/api/jobs/${jobId}`);
    if (s.status === "done") return showResults(s);
    if (["error", "cancelled"].includes(s.status)) return showError(s.message);
    setTimeout(() => pollOnce(jobId), 800);
  } catch (err) {
    // El job sigue en el server; toleramos cortes transitorios y sólo
    // mostramos error tras varios intentos fallidos seguidos.
    if (failures >= 5) return showError(err.message);
    setTimeout(() => pollOnce(jobId, failures + 1), 1000);
  }
}

function setProgress(frac) {
  const pct = Math.round((frac || 0) * 100);
  progFill.style.width = pct + "%"; progPct.textContent = pct + "%";
}
function eta(frac) {
  if (!frac || frac < 0.02) return "";
  const elapsed = (Date.now() - state.startedAt) / 1000;
  const remain = elapsed / frac - elapsed;
  const m = Math.floor(remain / 60), s = Math.round(remain % 60);
  return t("fn.eta")(m, String(s).padStart(2, "0"));
}

$("#cancelBtn").addEventListener("click", async () => {
  if (state.jobId) { try { await api(`/api/jobs/${state.jobId}`, { method: "DELETE" }); } catch {} }
});

// --- Resultados ------------------------------------------------------------
function showResults(s) {
  stopPhrases();
  state.lastStatus = s;
  processing.classList.add("hidden");
  errorBox.classList.add("hidden");
  results.classList.remove("hidden");
  goStep(4);
  renderResults(s);
}

function fmtTime(sec) {
  sec = Math.max(0, Math.round(sec || 0));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const mm = h ? String(m).padStart(2, "0") : String(m);
  return (h ? `${h}:` : "") + `${mm}:${String(s).padStart(2, "0")}`;
}

function renderTimeline(duration) {
  const wrap = $("#timelineWrap"), tl = $("#timeline");
  tl.innerHTML = "";
  if (!duration || state.ranges.length === 0) { wrap.classList.add("hidden"); return; }
  wrap.classList.remove("hidden");
  $("#tlEnd").textContent = fmtTime(duration);
  state.ranges.forEach((r) => {
    const seg = document.createElement("button");
    seg.type = "button";
    seg.className = "timeline-seg";
    seg.style.left = (100 * r.start / duration) + "%";
    seg.style.width = Math.max(0.7, 100 * (r.end - r.start) / duration) + "%";
    seg.title = `${r.range_label} · ${t("fn.frames")(r.count)}`;
    seg.onclick = (e) => { e.stopPropagation(); jumpTo(r); };
    tl.appendChild(seg);
  });
}

function renderResults(s) {
  state.ranges = s.ranges || [];
  $("#resTitle").textContent = t("fn.found")(state.ranges.length);

  const player = $("#localPlayer");
  if (state.videoKind === "local" && state.videoFile) {
    if (!state.localUrl) state.localUrl = URL.createObjectURL(state.videoFile);
    player.src = state.localUrl; player.classList.remove("hidden");
  } else { player.classList.add("hidden"); }

  renderTimeline(s.duration);

  const grid = $("#rangesGrid");
  grid.innerHTML = "";
  $("#noMatches").classList.toggle("hidden", state.ranges.length > 0);

  state.ranges.forEach((r) => {
    const card = document.createElement("div");
    card.className = "range-card";

    const media = document.createElement("div");
    media.className = "rc-media";
    const base = document.createElement(r.thumbnail_url ? "img" : "div");
    base.className = "rc-thumb";
    if (r.thumbnail_url) { base.src = r.thumbnail_url; base.alt = ""; }
    media.appendChild(base);

    // Mini-clip: se carga (lazy) al pasar el mouse y se reproduce en loop.
    if (r.clip_url) {
      card.classList.add("has-clip");
      let clip = null;
      const play = () => {
        if (!clip) {
          clip = document.createElement("img");
          clip.className = "rc-clip"; clip.alt = "";
          clip.src = r.clip_url;
          media.appendChild(clip);
        }
        media.classList.add("playing");
      };
      card.addEventListener("mouseenter", play);
      card.addEventListener("mouseleave", () => media.classList.remove("playing"));
    }

    const body = document.createElement("div");
    body.className = "rc-body";
    body.innerHTML = `
      <div class="rc-time">${r.range_label}</div>
      <div class="rc-meta"><span>${t("fn.frames")(r.count)}</span></div>`;

    card.append(media, body);
    card.onclick = () => jumpTo(r);
    grid.appendChild(card);
  });
}

function jumpTo(r) {
  if (state.videoKind === "youtube" && r.seek_url) {
    window.open(r.seek_url, "_blank", "noopener");
  } else if (state.videoKind === "local") {
    const player = $("#localPlayer");
    player.currentTime = r.best_timestamp; player.play();
    player.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function showError(msg) {
  stopPhrases();
  processing.classList.add("hidden");
  results.classList.add("hidden");
  errorBox.classList.remove("hidden");
  $("#errMsg").textContent = msg;
}

$("#retryBtn").addEventListener("click", () => goStep(3));
$("#newSearch").addEventListener("click", () => location.reload());

// --- init ------------------------------------------------------------------
applyI18n();
goStep(1);
