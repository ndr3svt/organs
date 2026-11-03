import { loadData } from './data.js?v=f241b670';
import { $, el, fmt } from './dom.js?v=f241b670';
import { renderRealms } from './realms.js?v=f241b670';
import { initSpecimen } from './specimen.js?v=f241b670';
import { renderCharts } from './charts.js?v=f241b670';
import { renderCredits } from './credits.js?v=f241b670';

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
