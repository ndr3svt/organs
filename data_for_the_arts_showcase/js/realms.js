// 01 Realms: one row per realm with its count, its share of the collection and a strip of tiles.
import { $, el, fmt } from './dom.js?v=f241b670';

const TILES = 16;

export function renderRealms(data, { onRealm, onPick }) {
  const list = $('#realm-list');
  const total = data.aggregates.total;
  const rows = new Map();

  for (const realm of data.realms) {
    const shown = data.specimens.filter((s) => s.realm === realm.id);
    const collected = data.aggregates.funnel[realm.id].collected;
    const step = Math.max(1, Math.floor(shown.length / TILES));
    const tiles = shown.filter((_, i) => i % step === 0).slice(0, TILES);

    const name = el(
      'button',
      { type: 'button', class: 'realm-name', 'aria-pressed': 'false', onclick: () => onRealm(realm.id) },
      el('span', { class: 'sw', vars: { '--c': realm.color }, 'aria-hidden': 'true' }),
      realm.id
    );
    const strip = el(
      'div',
      { class: 'strip' },
      tiles.map((s) =>
        el(
          'button',
          { type: 'button', class: 'tile', 'data-id': s.id, 'aria-label': `Show ${s.title}`, onclick: () => onPick(s.id) },
          el('img', { src: data.url('tile', s.id), alt: '', loading: 'lazy', decoding: 'async', width: 128, height: 128 })
        )
      )
    );
    const row = el(
      'li',
      { class: 'realm' },
      el(
        'div',
        { class: 'realm-head' },
        el('span', { class: 'idx' }, String(realm.index).padStart(2, '0')),
        name,
        el('span', { class: 'count' }, fmt(collected)),
        el('span', { class: 'share', vars: { '--c': realm.color, '--w': `${(100 * collected) / total}%` } }, el('i'))
      ),
      strip
    );
    rows.set(realm.id, { row, name, strip });
    list.append(row);
  }

  return {
    // Reflect the current filter and the specimen on show.
    update({ realm, id }) {
      for (const [key, r] of rows) {
        r.row.classList.toggle('is-active', key === realm);
        r.name.setAttribute('aria-pressed', String(key === realm));
        for (const tile of r.strip.children) tile.setAttribute('aria-current', String(tile.dataset.id === id));
      }
    },
  };
}
