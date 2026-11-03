// 02 Specimen: a slider through the cutouts, and a second slider that moves one specimen
// from the source photograph to the cutout to the class mask.
import { $, el, safeUrl } from './dom.js?v=22f63765';
import { LICENSE_LABEL, LICENSE_URL, SOURCE_LABEL } from './data.js?v=22f63765';

const NOTES = [
  ['source', 'The photograph as found: an organ in a jar, in a dish, on a forest floor. Backgrounds differ, and a model would learn the backgrounds as much as the organs.'],
  ['cutout', 'The background is removed and the organ is centred on one neutral ground. What is left is the form and the surface, nothing around it.'],
  ['mask', 'The outline, painted in the color of its realm. This is what the model will be given: a silhouette and a class, nothing else.'],
];

export function initSpecimen(data, { onShow }) {
  const range = $('#specimen-range');
  const proc = $('#process-range');
  const plate = $('#plate');
  const layers = { source: $('#img-source'), cutout: $('#img-cutout'), mask: $('#img-mask') };
  const readout = $('#n');
  const of = $('#of');
  const caption = $('#caption');
  const ticks = $('#ticks');
  const stepLabels = [...document.querySelectorAll('#steps [data-step]')];
  const stepNote = $('#step-note');

  let realm = null;
  let list = data.specimens;
  let pos = 0;
  let token = 0;

  const pad = (n) => String(n).padStart(4, '0');

  function renderTicks() {
    ticks.replaceChildren();
    if (realm) return; // a single realm needs no markers
    let start = 0;
    for (const r of data.realms) {
      const count = list.filter((s) => s.realm === r.id).length;
      if (count) ticks.append(el('span', { class: 'tick', vars: { '--x': (start / Math.max(1, list.length - 1)).toFixed(4) } }, r.id));
      start += count;
    }
  }

  function renderCaption(s) {
    const source = safeUrl(s.url);
    const licenseUrl = LICENSE_URL[s.license];
    caption.replaceChildren(
      el('span', { class: 'title' }, s.title),
      `${s.author} · `,
      licenseUrl ? el('a', { href: licenseUrl, target: '_blank', rel: 'noopener noreferrer' }, LICENSE_LABEL[s.license]) : LICENSE_LABEL[s.license],
      ' · ',
      source ? el('a', { href: source, target: '_blank', rel: 'noopener noreferrer' }, SOURCE_LABEL[s.source] ?? s.source) : (SOURCE_LABEL[s.source] ?? s.source)
    );
  }

  function preload(i) {
    const s = list[i];
    if (!s) return;
    for (const kind of ['cutout', 'source', 'mask']) new Image().src = data.url(kind, s.id);
  }

  async function show(i) {
    pos = Math.max(0, Math.min(list.length - 1, i));
    const s = list[pos];
    const mine = ++token;

    readout.textContent = pad(pos + 1);
    of.textContent = `/ ${pad(list.length)}`;
    range.value = String(pos + 1);
    range.setAttribute('aria-valuetext', `${pos + 1} of ${list.length}: ${s.title}`);
    renderCaption(s);
    layers.cutout.alt = `${s.title}, cutout on a neutral ground`;
    onShow({ realm, id: s.id });

    // Swap all three layers together, only once they have loaded, and only if this is still the latest request.
    const pending = Object.entries(layers).map(async ([kind, img]) => {
      const next = new Image();
      next.src = data.url(kind, s.id);
      try { await next.decode(); } catch { /* shown anyway when it arrives */ }
      return [img, next.src];
    });
    const ready = await Promise.all(pending);
    if (mine !== token) return;
    for (const [img, src] of ready) img.src = src;

    preload(pos - 1);
    preload(pos + 1);
  }

  function setProcess(value) {
    plate.style.setProperty('--p', String(value));
    const step = Math.round(value);
    stepLabels.forEach((label, i) => label.setAttribute('aria-current', String(i === step)));
    stepNote.textContent = NOTES[step][1];
    proc.setAttribute('aria-valuetext', NOTES[step][0]);
  }

  // Slider input is coalesced to one render per frame, so fast scrubbing stays smooth.
  let raf = 0;
  range.addEventListener('input', () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => show(Number(range.value) - 1));
  });
  range.addEventListener('keydown', (event) => {
    if (event.key !== 'PageUp' && event.key !== 'PageDown') return;
    event.preventDefault();
    show(pos + (event.key === 'PageUp' ? 10 : -10));
  });
  proc.addEventListener('input', () => setProcess(Number(proc.value)));

  setProcess(Number(proc.value));
  range.max = String(list.length);
  renderTicks();
  show(0);

  return {
    // Limit the slider to one realm (or all, with null), keeping the specimen if it is still in the list.
    setRealm(next, keepId) {
      realm = next;
      list = realm ? data.specimens.filter((s) => s.realm === realm) : data.specimens;
      range.max = String(list.length);
      renderTicks();
      const at = list.findIndex((s) => s.id === keepId);
      return show(at >= 0 ? at : 0);
    },
    // Jump to a specimen, widening the list if it belongs to another realm.
    showId(id) {
      let at = list.findIndex((s) => s.id === id);
      if (at < 0) {
        realm = null;
        list = data.specimens;
        range.max = String(list.length);
        renderTicks();
        at = list.findIndex((s) => s.id === id);
      }
      return show(at);
    },
    get realm() {
      return realm;
    },
  };
}
