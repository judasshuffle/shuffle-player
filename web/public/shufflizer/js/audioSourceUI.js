export function initAudioSourceUI(audioEl) {
  const $ = (id) => document.getElementById(id);

  const els = {
    mode: $("audioMode"),
    url: $("audioUrl"),
    connect: $("audioConnect"),
    file: $("audioFile"),
    pick: $("audioPickFile"),
    status: $("audioStatus"),
  };

  if (!els.mode) return;

  function setStatus(msg) {
    if (els.status) els.status.textContent = msg || "";
  }

  function showForMode(mode) {
    const showUrl = (mode === "custom");
    const showFile = (mode === "file");

    if (els.url) els.url.style.display = showUrl ? "" : "none";
    if (els.connect) els.connect.style.display = showUrl ? "" : "none";
    if (els.pick) els.pick.style.display = showFile ? "" : "none";
  }

  async function useUrl(url) {
    try { audioEl.crossOrigin = "anonymous"; } catch {}
    try { audioEl.pause(); } catch {}
    audioEl.src = url;
    try { audioEl.load(); } catch {}

    // Autoplay may be blocked until user clicks once — that's fine.
    try { await audioEl.play(); }
    catch { setStatus("Click once to allow audio playback, then try again."); }
  }

  async function applyFromSettings(settings) {
    const audio = (settings && settings.audio) || {};
    const mode = audio.mode || "stream";

    els.mode.value = mode;
    showForMode(mode);

    if (mode === "stream") {
      await useUrl(audio.streamUrl || "/stream.mp3");
      setStatus(`Using stream: ${audio.streamUrl || "/stream.mp3"}`);
    } else if (mode === "custom") {
      if (els.url) els.url.value = audio.customUrl || "";
      setStatus("Enter URL and click Connect.");
    } else if (mode === "file") {
      setStatus("Choose a local file…");
    }
  }

  els.mode.addEventListener("change", () => {
    const mode = els.mode.value;
    window.ShufflizerSettings?.set?.({ audio: { mode } });
    applyFromSettings(window.ShufflizerSettings?.get?.());
  });

  els.connect?.addEventListener("click", async () => {
    const url = (els.url?.value || "").trim();
    if (!url) { setStatus("Please enter a URL."); return; }
    window.ShufflizerSettings?.set?.({ audio: { mode: "custom", customUrl: url } });
    setStatus("Connecting…");
    await useUrl(url);
    setStatus("Connected (custom URL).");
  });

  els.pick?.addEventListener("click", () => els.file?.click());

  els.file?.addEventListener("change", async () => {
    const f = els.file?.files?.[0];
    if (!f) return;
    const objUrl = URL.createObjectURL(f);
    window.ShufflizerSettings?.set?.({ audio: { mode: "file" } });
    setStatus(`Loading: ${f.name}`);
    await useUrl(objUrl);
    setStatus(`Playing: ${f.name}`);
  });

  window.addEventListener("shufflizer:settings-ready", (e) => {
    applyFromSettings(e.detail);
  });

  // If settings already loaded before this module ran, apply immediately.
  const cur = window.ShufflizerSettings?.get?.();
  if (cur) applyFromSettings(cur);
}
