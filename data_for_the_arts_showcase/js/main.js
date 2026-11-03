import { loadData } from './data.js?v=22f63765';
import { $, el, fmt } from './dom.js?v=22f63765';
import { renderRealms } from './realms.js?v=22f63765';
import { initSpecimen } from './specimen.js?v=22f63765';
import { renderCharts } from './charts.js?v=22f63765';
import { renderCredits } from './credits.js?v=22f63765';

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
