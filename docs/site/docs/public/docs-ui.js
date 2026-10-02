// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
(() => {
  // Development/SPA uses VitePress's own handlers. Built MPA has none.
  if (document.querySelector('script[type="module"]')) return;
  const root = document.documentElement;
  const base = new URL('.', document.currentScript.src);

  function updateAppearance() {
    const dark = root.classList.contains('dark');
    for (const button of document.querySelectorAll('.VPSwitchAppearance')) {
      button.setAttribute('aria-checked', String(dark));
      button.title = dark ? 'Switch to light theme' : 'Switch to dark theme';
    }
  }
  updateAppearance();
  for (const button of document.querySelectorAll('.VPSwitchAppearance')) {
    button.addEventListener('click', () => {
      const dark = root.classList.toggle('dark');
      try { localStorage.setItem('vitepress-theme-appearance', dark ? 'dark' : 'light'); } catch {}
      updateAppearance();
    });
  }

  function dialog(title, id) {
    const element = document.createElement('dialog');
    element.className = 'docs-popover'; element.id = id;
    const heading = document.createElement('h2');
    heading.id = id + '-title'; heading.textContent = title;
    element.setAttribute('aria-labelledby', heading.id);
    const close = document.createElement('button');
    close.className = 'docs-close'; close.textContent = 'Close';
    close.addEventListener('click', () => element.close());
    element.append(heading, close); document.body.append(element);
    element.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); element.close(); }
    });
    element.addEventListener('click', event => {
      const box = element.getBoundingClientRect();
      if (event.target === element && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) element.close();
    });
    return element;
  }

  const menu = dialog('Navigation', 'VPNavScreen');
  const menuBody = document.createElement('nav');
  menuBody.setAttribute('aria-label', 'Documentation navigation');
  for (const item of document.querySelector('.VPNavBarMenu')?.children || []) {
    if (item.matches('a')) menuBody.append(item.cloneNode(true));
    else if (item.matches('.VPNavBarMenuGroup')) {
      const group = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = item.querySelector('button .text > span:not([class])')?.textContent || item.querySelector('button .text')?.textContent;
      group.append(summary);
      for (const link of item.querySelectorAll('.VPMenu a')) group.append(link.cloneNode(true));
      menuBody.append(group);
    }
  }
  menu.append(menuBody);
  const hamburger = document.querySelector('.VPNavBarHamburger');
  if (hamburger) {
    hamburger.addEventListener('click', () => { menu.showModal(); hamburger.setAttribute('aria-expanded', 'true'); });
    menu.addEventListener('close', () => hamburger.setAttribute('aria-expanded', 'false'));
  }

  const search = dialog('Search documentation', 'docs-search');
  const label = document.createElement('label'); label.textContent = 'Search terms'; label.htmlFor = 'docs-search-input';
  const input = document.createElement('input'); input.type = 'search'; input.id = label.htmlFor;
  const status = document.createElement('p'); status.setAttribute('role', 'status');
  const results = document.createElement('ul'); results.className = 'docs-search-results';
  search.append(label, input, status, results);
  let pages;
  async function openSearch() {
    search.showModal(); input.focus();
    if (!pages) {
      status.textContent = 'Loading local documentation index…';
      try {
        const response = await fetch(new URL('docs-search.json', base));
        if (!response.ok) throw new Error('Index unavailable');
        pages = await response.json(); renderSearch();
      } catch { status.textContent = 'Search index unavailable. Use the navigation menu.'; }
    }
  }
  function renderSearch() {
    results.replaceChildren();
    const terms = input.value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
    if (!terms.length) { status.textContent = 'Enter terms to search this site.'; return; }
    const matches = pages.filter(page => terms.every(term => (page.title + ' ' + page.text).toLocaleLowerCase().includes(term))).slice(0, 12);
    status.textContent = matches.length ? `${matches.length} results shown` : 'No matching pages';
    for (const page of matches) {
      const row = document.createElement('li'), link = document.createElement('a');
      link.href = new URL(page.href, base).href; link.textContent = page.title;
      row.append(link); results.append(row);
    }
  }
  input.addEventListener('input', () => { if (pages) renderSearch(); });
  document.querySelector('.DocSearch-Button')?.addEventListener('click', openSearch);
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault(); if (!search.open) openSearch();
    }
  });

  for (const button of document.querySelectorAll('button.copy')) {
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(button.parentElement.querySelector('code').textContent);
        button.title = 'Copied'; button.setAttribute('aria-label', 'Copied');
        setTimeout(() => { button.title = 'Copy Code'; button.setAttribute('aria-label', 'Copy Code'); }, 2000);
      } catch { button.title = 'Select code to copy'; button.setAttribute('aria-label', 'Select code to copy'); }
    });
  }
})();
