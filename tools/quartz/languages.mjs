import { readFileSync, writeFileSync, rmSync, cpSync, mkdirSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { load } from 'cheerio';
import { redirect } from './compat.mjs';
import { root } from './paths.mjs';

export const translations = [
  { slug: 'qwen3-tts-streaming/optimization', zh: 'qwen3-tts-streaming/optimization.zh.md', en: 'qwen3-tts-streaming/optimization.en.md' },
];
const walk = dir => readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]);
export function prepareLanguages(input) {
  const english = new Map();
  for (const entry of translations) {
    english.set(entry.slug, readFileSync(path.join(input, entry.en), 'utf8').replace(/^.*· \[中文版\].*\n/gm, ''));
    const zh = readFileSync(path.join(input, entry.zh), 'utf8').replace(/^.*· \[English\].*\n/gm, '');
    writeFileSync(path.join(input, `${entry.slug}.md`), zh);
    rmSync(path.join(input, entry.zh));
    rmSync(path.join(input, entry.en));
  }
  // All content links point to the single indexed article before Quartz builds its graph.
  for (const file of walk(input).filter(f => f.endsWith('.md'))) {
    let text = readFileSync(file, 'utf8');
    for (const entry of translations) {
      const name = path.basename(entry.slug);
      text = text.replaceAll(`${name}.zh.md`, `${name}.md`).replaceAll(`${name}.en.md`, `${name}.md#article-language-en`);
    }
    writeFileSync(file, text);
  }
  return english;
}
export function mergeLanguages(output, englishOutput) {
  for (const entry of translations) {
    const file = path.join(output, `${entry.slug}.html`);
    const $ = load(readFileSync(file, 'utf8'));
    const en = load(readFileSync(path.join(englishOutput, `${entry.slug}.html`), 'utf8'));
    const title = $('.article-title').first();
    title.attr('data-title-zh', title.text()).attr('data-title-en', en('.article-title').first().text());
    $('article').first().wrapInner('<div data-article-lang="zh" lang="zh-CN"></div>');
    const panel = $('<div data-article-lang="en" lang="en" hidden></div>').html(en('article').first().html());
    // Namespace translated anchors, including footnotes, to keep every DOM ID unique.
    panel.find('[id]').not('#mermaid-container, #mermaid-space').each((_, e) => $(e).attr('id', `en-${$(e).attr('id')}`));
    panel.find('[href^="#"]').each((_, e) => $(e).attr('href', `#en-${$(e).attr('href').slice(1)}`));
    $('article').first().append(panel);
    $('article').first().before('<nav class="article-languages" aria-label="文章语言 / Article language"><button type="button" data-set-lang="zh" aria-pressed="true">中文</button><button type="button" data-set-lang="en" aria-pressed="false">English</button></nav>');
    const toc = $('div.toc').first();
    if (toc.length) {
      toc.attr('data-article-lang', 'zh');
      const englishToc = $(en('div.toc').first().toString()).attr('data-article-lang', 'en').attr('hidden', '');
      englishToc.find('[id]').each((_, e) => $(e).attr('id', `en-${$(e).attr('id')}`));
      englishToc.find('[href^="#"]').each((_, e) => $(e).attr('href', `#en-${$(e).attr('href').slice(1)}`));
      englishToc.find('[data-for]').each((_, e) => $(e).attr('data-for', `en-${$(e).attr('data-for')}`));
      toc.after(englishToc);
    }

    writeFileSync(file, $.html());
    const indexPath = path.join(output, 'static/contentIndex.json');
    const index = JSON.parse(readFileSync(indexPath, 'utf8'));
    index[entry.slug].content += '\n' + en('article').text();
    writeFileSync(indexPath, JSON.stringify(index));
    for (const lang of ['zh', 'en']) {
      cpSync(path.join(root, 'blogs', entry[lang]), path.join(output, entry[lang]));
      const target = `${path.basename(entry.slug)}?lang=${lang}`;
      // Explicit language plus preserved fragments for bookmarks to the old pages.
      const html = redirect(target).replace('+location.search+location.hash', '+(location.search ? "&"+location.search.slice(1) : "")+location.hash');
      writeFileSync(path.join(output, `${entry.slug}.${lang}.html`), html);
    }
  }
  for (const file of walk(output).filter(f => f.endsWith('.html'))) {
    const $ = load(readFileSync(file, 'utf8'));
    if (!$('article').length) continue;
    $('a[href$="#article-language-en"]').each((_, e) => $(e).attr('href', $(e).attr('href').replace('#article-language-en', '?lang=en')));
    const relative = path.relative(path.dirname(file), path.join(output, 'static')).split(path.sep).join('/');
    $('head').append(`<link rel="stylesheet" href="${relative}/languages.css" data-persist="true"><script src="${relative}/languages.js" defer data-persist="true"></script>`);
    writeFileSync(file, $.html());
  }
  mkdirSync(path.join(output, 'static'), { recursive: true });
  for (const name of ['languages.js', 'languages.css']) cpSync(new URL(`./${name}`, import.meta.url), path.join(output, 'static', name));
}
