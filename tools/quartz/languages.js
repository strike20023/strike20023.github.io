(() => {
  if (window.__articleLanguages) return;
  window.__articleLanguages = true;
  function selectLanguage(lang, updateURL = false) {
    if (!document.querySelector('.article-languages')) return;
    lang = lang === 'en' ? 'en' : 'zh';
    document.querySelectorAll('[data-article-lang]').forEach(el => { el.hidden = el.dataset.articleLang !== lang; });
    document.querySelectorAll('[data-set-lang]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.setLang === lang)));
    const title = document.querySelector('.article-title');
    if (title) { title.textContent = title.dataset[lang === 'en' ? 'titleEn' : 'titleZh']; document.title = title.textContent; }
    document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN';
    try { localStorage.setItem('article-language', lang); } catch {}
    if (updateURL) {
      const url = new URL(location.href); url.searchParams.set('lang', lang); url.hash = '';
      history.replaceState(null, '', url);
    }
  }
  function initialize() {
    if (!document.querySelector('.article-languages')) { document.documentElement.lang = 'zh-CN'; return; }
    let preferred = 'zh';
    try { preferred = localStorage.getItem('article-language') || 'zh'; } catch {}
    const query = new URLSearchParams(location.search).get('lang');
    selectLanguage(query || preferred);
    if (query === 'en' && location.hash && !location.hash.startsWith('#en-')) {
      const target = document.getElementById(`en-${decodeURIComponent(location.hash.slice(1))}`);
      if (target) { history.replaceState(null, '', `${location.pathname}${location.search}#${target.id}`); target.scrollIntoView(); }
    }
  }
  document.addEventListener('click', event => {
    const button = event.target.closest?.('[data-set-lang]');
    if (button) selectLanguage(button.dataset.setLang, true);
  });
  document.addEventListener('nav', initialize);
  window.addEventListener('popstate', initialize);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
