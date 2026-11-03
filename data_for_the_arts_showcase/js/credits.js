// 05 Credits: every shown image with its author, license and source. Built lazily, when the list is opened.
import { $, el, safeUrl } from './dom.js?v=a9a1ee1a';
import { LICENSE_LABEL, LICENSE_URL, SOURCE_LABEL } from './data.js?v=a9a1ee1a';

export function renderCredits(data) {
  const details = $('#credits-list');
  const items = $('#credits-items');
  $('#credits-count').textContent = `All ${data.specimens.length} credits`;

  let built = false;
  details.addEventListener('toggle', () => {
    if (!details.open || built) return;
    built = true;
    items.replaceChildren(
      ...data.specimens.map((s) => {
        const source = safeUrl(s.url);
        const licenseUrl = LICENSE_URL[s.license];
        return el(
          'li',
          {},
          el('span', {}, s.realm),
          source ? el('a', { href: source, target: '_blank', rel: 'noopener noreferrer' }, s.title) : el('span', {}, s.title),
          el('span', {}, s.author),
          licenseUrl ? el('a', { href: licenseUrl, target: '_blank', rel: 'noopener noreferrer' }, LICENSE_LABEL[s.license]) : el('span', {}, LICENSE_LABEL[s.license]),
          el('span', {}, SOURCE_LABEL[s.source] ?? s.source)
        );
      })
    );
  });
}
