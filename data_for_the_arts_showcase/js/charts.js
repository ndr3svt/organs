// 03 Numbers: three small figures drawn as inline SVG from the aggregates, each backed by a hidden table.
// Color is used only for the realms; everything else is ink at different strengths.
import { $, el, svg, fmt } from './dom.js?v=a9a1ee1a';
import { SOURCE_LABEL } from './data.js?v=a9a1ee1a';

const W = 1000; // svg user units; the svg stretches to its column
const H = 14;

// A table never shrinks below its content, so it cannot be hidden with width: 1px itself: it would still
// widen the page. The clipping wrapper does the hiding; the table stays available to screen readers.
function table(caption, head, rows) {
  return el(
    'div',
    { class: 'sr-only' },
    el(
      'table',
      {},
      el('caption', {}, caption),
      el('thead', {}, el('tr', {}, head.map((h) => el('th', { scope: 'col' }, h)))),
      el('tbody', {}, rows.map((r) => el('tr', {}, r.map((cell, i) => el(i ? 'td' : 'th', i ? {} : { scope: 'row' }, String(cell))))))
    )
  );
}

function figure(title, what, ...rest) {
  return el('figure', { class: 'chart' }, el('h3', {}, title), el('p', { class: 'what' }, what), ...rest.filter(Boolean));
}

function legend(items) {
  return el('ul', { class: 'legend' }, items.map(({ label, fill, hatch }) =>
    el('li', {}, el('i', { style: hatch ? 'background: repeating-linear-gradient(135deg, var(--fg) 0 1px, transparent 1px 4px)' : `background: ${fill}` }), label)));
}

// 1. Funnel: how many images survive each stage, per realm.
function funnel(data) {
  const f = data.aggregates.funnel;
  const max = Math.max(...Object.values(f).map((x) => x.collected));
  const rows = data.realms.map((r) => {
    const { collected, passed, kept } = f[r.id];
    const bar = svg('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'none', 'aria-hidden': 'true' },
      svg('rect', { x: 0, y: 0, width: (W * collected) / max, height: H, fill: 'var(--line-soft)' }),
      svg('rect', { x: 0, y: 0, width: (W * passed) / max, height: H, fill: 'var(--fg)' }),
      kept ? svg('rect', { x: 0, y: 0, width: Math.max(8, (W * kept) / max), height: H, fill: r.color }) : '');
    return el('div', { class: 'row' }, el('span', {}, r.id), bar,
      el('span', { class: 'vals' }, `${fmt(collected)} · ${fmt(passed)} · ${fmt(kept)}`));
  });
  return figure(
    'From collected to kept',
    'Each realm is drawn at the same scale. The pale bar is every image collected, the dark bar is what passed the automatic checks, and the colored mark is what a person has reviewed and kept so far. Most of the review is still to do.',
    ...rows,
    legend([
      { label: 'collected', fill: 'var(--line-soft)' },
      { label: 'passed the automatic checks', fill: 'var(--fg)' },
      { label: 'kept by a person, in the color of its realm', fill: data.realms[0].color },
    ]),
    table('Images per stage and realm', ['Realm', 'Collected', 'Passed checks', 'Kept'],
      data.realms.map((r) => [r.id, f[r.id].collected, f[r.id].passed, f[r.id].kept]))
  );
}

// 2. A 100% bar per realm for any categorical mix, drawn in tints of ink.
function mixFigure(data, { title, what, mix, order, label, tint, hatched = () => false, tableCaption }) {
  const rows = data.realms.map((r) => {
    const counts = mix[r.id];
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    let x = 0;
    const parts = order.filter((k) => counts[k]).map((k) => {
      const w = (W * counts[k]) / total;
      const node = svg('rect', { x, y: 0, width: w, height: H, fill: hatched(k) ? 'url(#hatch)' : 'var(--fg)', 'fill-opacity': tint(k) });
      x += w;
      return node;
    });
    const bar = svg('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'none', 'aria-hidden': 'true' }, ...parts);
    const lead = order.reduce((best, k) => ((counts[k] || 0) > (counts[best] || 0) ? k : best), order[0]);
    return el('div', { class: 'row' }, el('span', {}, r.id), bar,
      el('span', { class: 'vals' }, `${label(lead)} ${Math.round((100 * counts[lead]) / total)}%`));
  });
  // The hatch pattern is defined once, by the figure that uses it.
  const defs = order.some(hatched)
    ? svg('svg', { width: 0, height: 0, 'aria-hidden': 'true', style: 'position:absolute' },
      svg('defs', {}, svg('pattern', { id: 'hatch', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' },
        svg('rect', { width: 6, height: 6, fill: 'var(--bg)' }), svg('rect', { width: 1.2, height: 6, fill: 'var(--fg)' }))))
    : null;
  return figure(title, what, defs, ...rows,
    legend(order.map((k) => ({ label: label(k), fill: `rgba(11, 11, 22, ${tint(k)})`, hatch: hatched(k) }))),
    table(tableCaption, ['Realm', ...order.map(label)], data.realms.map((r) => [r.id, ...order.map((k) => mix[r.id][k] || 0)])));
}

const LICENSES = ['cc0', 'pdm', 'by', 'by-sa', 'by-nc', 'by-nc-sa'];
const LICENSE_NAME = { cc0: 'CC0', pdm: 'public domain', by: 'CC BY', 'by-sa': 'CC BY-SA', 'by-nc': 'CC BY-NC', 'by-nc-sa': 'CC BY-NC-SA' };
const LICENSE_TINT = { cc0: 0.28, pdm: 0.42, by: 0.6, 'by-sa': 0.82, 'by-nc': 1, 'by-nc-sa': 1 };

export function renderCharts(data) {
  const a = data.aggregates;
  $('#charts').replaceChildren(
    funnel(data),
    mixFigure(data, {
      title: 'Licenses',
      what: `Every image keeps the license its author chose. The hatched parts are non-commercial: ${fmt(a.non_commercial)} images, ${Math.round((100 * a.non_commercial) / a.total)}% of the collection. They are used for study, and they are not shown on this page.`,
      mix: a.license,
      order: LICENSES.filter((k) => data.realms.some((r) => a.license[r.id][k])),
      label: (k) => LICENSE_NAME[k],
      tint: (k) => LICENSE_TINT[k],
      hatched: (k) => k.includes('nc'),
      tableCaption: 'Images per license and realm',
    }),
    mixFigure(data, {
      title: 'Sources',
      what: 'Where each realm comes from. Wikimedia Commons supplies most of every realm. iNaturalist adds wild mushrooms and some flowers and fruits, and the Wellcome Collection a few specimens. Each bar is labeled with its largest source.',
      mix: a.source,
      order: Object.keys(SOURCE_LABEL).filter((k) => data.realms.some((r) => a.source[r.id][k])),
      label: (k) => SOURCE_LABEL[k],
      tint: (k) => ({ commons: 0.3, inat: 0.65, wellcome: 1 })[k] ?? 0.5,
      tableCaption: 'Images per source and realm',
    })
  );
}
