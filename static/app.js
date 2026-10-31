const $ = (s) => document.querySelector(s);
const PANES = ["raw", "polished", "minuta"];
const S = {};

function resetState() {
  Object.assign(S, { jobId: null, es: null, total: 0, chunkSeconds: 600, polish: true,
    done: { raw: 0, polished: 0 }, minutaDone: false, ready: {}, blocks: { raw: {}, polished: {} },
    minuta: "", t0: 0, timer: null, finished: false });
}
resetState();

const fmt = (s) => { s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60);
  return (h ? String(h).padStart(2, "0") + ":" : "") + String(m).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); };

function setStatus(msg, cls = "") { const el = $("#status"); el.textContent = msg; el.className = "status " + cls; }
function setBar(p) { $("#barFill").style.width = Math.min(100, p) + "%"; }

/* ---------- Pestañas, copiar, descargas ---------- */
function showPane(name) {
  document.querySelectorAll("[role=tab]").forEach((b) => b.setAttribute("aria-selected", b.dataset.pane === name));
  PANES.forEach((p) => ($("#pane-" + p).hidden = p !== name));
}
document.querySelectorAll("[role=tab]").forEach((b) => b.addEventListener("click", () => showPane(b.dataset.pane)));

const KIND = { raw: "raw", polished: "transcript", minuta: "minuta" };
$("#copy").addEventListener("click", async () => {
  const pane = PANES.find((p) => !$("#pane-" + p).hidden);
  let text = $("#pane-" + pane).innerText;
  if (S.ready[KIND[pane]]) text = await (await fetch(`/api/jobs/${S.jobId}/files/${KIND[pane]}`)).text();
  await navigator.clipboard.writeText(text);
  $("#copy").textContent = "Copiado"; setTimeout(() => ($("#copy").textContent = "Copiar"), 1500);
});
function enableDownload(kind) {
  S.ready[kind] = true; const a = $("#dl-" + kind);
  a.href = `/api/jobs/${S.jobId}/files/${kind}`; a.setAttribute("aria-disabled", "false");
}

/* ---------- Render ---------- */
function block(stage, n) {
  const map = S.blocks[stage];
  if (!map[n]) {
    const pane = $("#pane-" + stage); pane.querySelector(".empty")?.remove();
    const div = document.createElement("div"); div.className = "block writing";
    div.innerHTML = `<h4>Bloque ${n} · desde ${fmt((n - 1) * S.chunkSeconds)}</h4><p></p>`;
    pane.appendChild(div); map[n] = div;
  }
  return map[n];
}
function stick(pane, fn) { const near = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 120; fn(); if (near) pane.scrollTop = pane.scrollHeight; }

function md(src) {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inl = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\[ \]/g, "☐").replace(/\[x\]/gi, "☑");
  const out = []; let list = null; const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
  for (const line of src.split("\n")) {
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)/))) { close(); const n = m[1].length + 1; out.push(`<h${n}>${inl(m[2])}</h${n}>`); }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inl(m[1])}</li>`); }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${inl(m[1])}</li>`); }
    else if (!line.trim()) close();
    else { close(); out.push(`<p>${inl(line)}</p>`); }
  }
  close(); return out.join("");
}

function updateProgress() {
  if (!S.total) return;
  const parts = S.polish ? 2 : 1;
  const p = ((S.done.raw + (S.polish ? S.done.polished : 0)) / (parts * S.total)) * 90 + (S.minutaDone ? 10 : 0);
  setBar(p);
  $("#stChunks").textContent = `${S.done.raw}/${S.total}`;
}

/* ---------- Eventos del servidor ---------- */
function listen(jobId) {
  const es = (S.es = new EventSource(`/api/jobs/${jobId}/events`));
  const on = (t, fn) => es.addEventListener(t, (e) => fn(JSON.parse(e.data)));
  const end = () => { es.close(); S.finished = true; clearInterval(S.timer); $("#cancel").hidden = true; $("#again").hidden = false; };

  on("status", (d) => setStatus(d.message, "live"));
  on("meta", (d) => { S.total = d.total_chunks; S.chunkSeconds = d.chunk_seconds; S.polish = d.polish;
    $("#stDur").textContent = d.duration ? fmt(d.duration) : "–"; updateProgress(); });
  on("delta", (d) => {
    if (d.stage === "minuta") { S.minuta += d.text; const p = $("#pane-minuta"); p.querySelector(".empty")?.remove();
      stick(p, () => (p.innerHTML = md(S.minuta))); return; }
    const b = block(d.stage, d.chunk), pane = $("#pane-" + d.stage);
    stick(pane, () => (b.querySelector("p").textContent += d.text));
  });
  on("reset", (d) => {
    if (d.stage === "minuta") { S.minuta = ""; $("#pane-minuta").innerHTML = ""; return; }
    if (S.blocks[d.stage][d.chunk]) S.blocks[d.stage][d.chunk].querySelector("p").textContent = "";
  });
  on("chunk_done", (d) => {
    S.done[d.stage]++; const b = S.blocks[d.stage][d.chunk];
    if (b) { b.classList.remove("writing"); if (d.empty) b.querySelector("p").textContent = "(sin voz en este bloque)"; }
    updateProgress();
  });
  on("files_ready", () => { enableDownload("raw"); enableDownload("transcript"); setStatus("Transcripción lista. Generando minuta…", "live"); });
  on("done", () => { S.minutaDone = true; enableDownload("minuta"); setBar(100); setStatus("Listo. Archivos guardados en la carpeta outputs.", "ok"); end(); });
  on("job_error", (d) => { setStatus(d.message, "err"); end(); });
  on("cancelled", () => { setStatus("Proceso cancelado.", "err"); end(); });
}

/* ---------- Subida ---------- */
function startUpload(file) {
  resetState(); PANES.forEach((p) => ($("#pane-" + p).innerHTML = '<p class="empty">Esperando datos…</p>'));
  ["raw", "transcript", "minuta"].forEach((k) => { const a = $("#dl-" + k); a.removeAttribute("href"); a.setAttribute("aria-disabled", "true"); });
  $("#job").hidden = false; $("#drop").hidden = true; $("#fileName").textContent = file.name;
  $("#cancel").hidden = false; $("#again").hidden = true; setBar(0);
  ["#stChunks", "#stDur"].forEach((s) => ($(s).textContent = "–"));
  S.t0 = Date.now(); S.timer = setInterval(() => ($("#stTime").textContent = fmt((Date.now() - S.t0) / 1000)), 1000);

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/jobs");
  xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
  xhr.setRequestHeader("Content-Type", "application/octet-stream");
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) { setBar((e.loaded / e.total) * 100); setStatus(`Subiendo… ${Math.round((e.loaded / e.total) * 100)} %`, "live"); } };
  xhr.onload = () => {
    if (xhr.status !== 200) { let m = "No se pudo subir el archivo."; try { m = JSON.parse(xhr.responseText).detail || m; } catch {}
      setStatus(m, "err"); clearInterval(S.timer); $("#again").hidden = false; $("#cancel").hidden = true; return; }
    S.jobId = JSON.parse(xhr.responseText).job_id; setBar(0); setStatus("Archivo recibido. Preparando…", "live"); listen(S.jobId);
  };
  xhr.onerror = () => { setStatus("Se perdió la conexión con el servidor.", "err"); clearInterval(S.timer); $("#again").hidden = false; };
  xhr.send(file);
  S.xhr = xhr;
}

const drop = $("#drop"), input = $("#file");
input.addEventListener("change", () => input.files[0] && startUpload(input.files[0]));
drop.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), input.click()));
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => e.dataTransfer.files[0] && startUpload(e.dataTransfer.files[0]));

$("#cancel").addEventListener("click", () => {
  if (S.jobId) fetch(`/api/jobs/${S.jobId}/cancel`, { method: "POST" });
  else S.xhr?.abort();
  if (!S.jobId) { clearInterval(S.timer); setStatus("Subida cancelada.", "err"); $("#cancel").hidden = true; $("#again").hidden = false; }
});
$("#again").addEventListener("click", () => { S.es?.close(); input.value = ""; $("#job").hidden = true; $("#drop").hidden = false; showPane("raw"); });

fetch("/api/health").then((r) => r.json()).then((h) => {
  const problems = [];
  if (!h.api_key) problems.push("Falta GOOGLE_API_KEY en el archivo .env.");
  if (!h.ffmpeg) problems.push("ffmpeg/ffprobe no está instalado o no está en el PATH.");
  if (problems.length) { const b = $("#banner"); b.textContent = problems.join(" "); b.hidden = false; }
});
