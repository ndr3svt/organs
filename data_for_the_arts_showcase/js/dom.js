// Tiny DOM helpers. Titles, authors and URLs come from third-party sites, so they only ever go in
// through textContent and setAttribute, never innerHTML.

export const $ = (selector, root = document) => root.querySelector(selector);

export function el(tag, props = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'vars') for (const [name, v] of Object.entries(value)) node.style.setProperty(name, v);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  node.append(...kids.flat().filter((kid) => kid != null && kid !== false));
  return node;
}

export function svg(tag, props = {}, ...kids) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(props)) node.setAttribute(key, value);
  node.append(...kids);
  return node;
}

// Only http(s) links are ever made clickable.
export function safeUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
  } catch {
    return null;
  }
}

// Thousands with a narrow no-break space, so numbers stay one token and line up in tabular figures.
export const fmt = (n) => Math.round(n).toLocaleString('en').replace(/,/g, '\u202f');
