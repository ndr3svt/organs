import { loadData } from './data.js?v=a9a1ee1a';
import { $, el, fmt } from './dom.js?v=a9a1ee1a';
import { renderRealms } from './realms.js?v=a9a1ee1a';
import { initSpecimen } from './specimen.js?v=a9a1ee1a';
import { renderCharts } from './charts.js?v=a9a1ee1a';
import { renderCredits } from './credits.js?v=a9a1ee1a';

const meta = $('#meta');

try {
  const data = await loadData();

  const sources = new Set(Object.values(data.aggregates.source).flatMap((mix) => Object.keys(mix)));
  meta.replaceChildren(
    ...[
      `${fmt(data.aggregates.total)} images`,
      `${data.realms.length} realms`,
      `${sources.size} sources`,
      `${fmt(data.specimens.length)} shown`,
    ].map((text) => el('span', {}, text))
  );

  let specimen;
  let currentId = null;
  const realms = renderRealms(data, {
    // Choosing the active realm again lifts the filter.
    onRealm: (id) => specimen.setRealm(specimen.realm === id ? null : id, currentId),
    onPick: (id) => specimen.showId(id),
  });
  specimen = initSpecimen(data, {
    onShow: ({ realm, id }) => {
      currentId = id;
      realms.update({ realm, id });
    },
  });

  renderCharts(data);
  renderCredits(data);
} catch (error) {
  meta.textContent = `The data could not be loaded (${error.message}).`;
}
