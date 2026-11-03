// Loads showcase.json and adds lookups. The `v` in the file changes whenever the shown set changes,
// so image URLs bypass caches exactly when they should.

export async function loadData() {
  const response = await fetch('data/showcase.json?v=f241b670');
  if (!response.ok) throw new Error(`showcase.json: HTTP ${response.status}`);
  const data = await response.json();
  data.byId = new Map(data.specimens.map((s) => [s.id, s]));
  data.color = Object.fromEntries(data.realms.map((r) => [r.id, r.color]));
  data.url = (kind, id) => `img/${kind}/${id}.webp?v=${data.v}`;
  return data;
}

export const LICENSE_LABEL = {
  cc0: 'CC0',
  pdm: 'Public domain',
  by: 'CC BY',
  'by-sa': 'CC BY-SA',
  'by-nc': 'CC BY-NC',
  'by-nc-sa': 'CC BY-NC-SA',
};

export const LICENSE_URL = {
  cc0: 'https://creativecommons.org/publicdomain/zero/1.0/',
  pdm: 'https://creativecommons.org/publicdomain/mark/1.0/',
  by: 'https://creativecommons.org/licenses/by/4.0/',
  'by-sa': 'https://creativecommons.org/licenses/by-sa/4.0/',
};

export const SOURCE_LABEL = { commons: 'Wikimedia Commons', inat: 'iNaturalist', wellcome: 'Wellcome Collection' };
