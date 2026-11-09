"""One bounded, value-free DOM accessible-name procedure for browser tooling."""

# Fixed code only: page content is data and never becomes executable source.
DOM_NAME_JS = r"""
(element, cooperate = () => true) => {
  const norm = value => (value || '').replace(/\s+/g, ' ').trim().slice(0, 80);
  let remaining = 400;
  const take = () => remaining-- > 0 && cooperate();
  const blocked = new Set(['INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'SCRIPT', 'STYLE', 'NOSCRIPT']);
  const privateElement = e => e.isContentEditable ||
    ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(e.tagName)
    || !!(e.parentElement && e.parentElement.closest('textarea,select,script,style,noscript'));
  const visible = e => !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
  const text = (root, hidden) => {
    if (privateElement(root) || blocked.has(root.tagName) || (!hidden && !visible(root))) return '';
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: node => node.nodeType === Node.ELEMENT_NODE &&
        (privateElement(node) || blocked.has(node.tagName) || (!hidden && !visible(node)))
          ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
    });
    let node = root, out = '';
    while (node && out.length < 160 && take()) {
      if (node.nodeType === Node.TEXT_NODE) out += ' ' + (node.textContent || '').slice(0, 160);
      else if (node.tagName === 'IMG') out += ' ' + (node.getAttribute('alt') || '').slice(0, 80);
      node = walker.nextNode();
    }
    return norm(out);
  };
  const seen = new Set();
  const name = (e, hidden = false, depth = 0) => {
    if (!e || privateElement(e) || depth > 3 || seen.has(e) || !take()) return '';
    seen.add(e);
    const refs = (e.getAttribute('aria-labelledby') || '').slice(0, 4000).trim().split(/\s+/, 16);
    const referenced = refs.filter(Boolean).map(
      id => name(document.getElementById(id), true, depth + 1));
    const linked = norm(referenced.filter(Boolean).join(' '));
    if (linked) return linked;
    const aria = norm(e.getAttribute('aria-label'));
    if (aria) return aria;
    const labels = e.labels ? [...e.labels].slice(0, 16).map(label => text(label, true)) : [];
    const native = norm(labels.filter(Boolean).join(' '));
    if (native) return native;
    const own = text(e, hidden);
    if (own) return own;
    // These input types display their value as the button caption; field values never name fields.
    if (e.tagName === 'INPUT' && ['button', 'submit', 'reset'].includes(e.type) && visible(e))
      return norm(e.value || e.getAttribute('title'));
    return norm(e.getAttribute('alt') || e.getAttribute('title') || e.getAttribute('placeholder'));
  };
  return name(element);
}
"""
