import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import path from 'node:path';
import { root, site } from './paths.mjs';
import { legacy } from './compat.mjs';

const files = dir => readdirSync(dir).flatMap(name => {
  const file = path.join(dir, name);
  return statSync(file).isDirectory() ? files(file) : [file];
});
const outputFiles = new Set(files(site));
const resolve = (base, href) => {
  const url = new URL(href, base);
  if (url.origin !== 'https://strike20023.github.io') return true;
  const pathname = decodeURIComponent(url.pathname);
  const file = path.join(site, pathname);
  return [file, `${file}.html`, path.join(file, 'index.html')].some(p => outputFiles.has(p));
};
let references = 0;
for (const file of files(site).filter(f => f.endsWith('.html'))) {
  const html = readFileSync(file, 'utf8');
  const base = `https://strike20023.github.io/${path.relative(site, file).split(path.sep).join('/')}`;
  for (const match of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
    const href = match[1].replaceAll('&amp;', '&');
    if (/^(?:#|data:|mailto:|tel:|javascript:)/.test(href)) continue;
    assert(resolve(base, href), `Broken HTML reference ${href} in ${path.relative(site, file)}`);
    references++;
  }
}
for (const folder of ['homepage', 'scripts', 'files']) {
  for (const file of files(path.join(root, folder))) {
    assert.deepEqual(readFileSync(path.join(site, path.relative(root, file))), readFileSync(file), `Changed public resource: ${file}`);
  }
}
for (const [old, source] of Object.entries(legacy)) {
  const output = path.join(site, old);
  assert(existsSync(output), `Missing legacy path: ${old}`);
  if (!source.endsWith('.md')) assert.deepEqual(readFileSync(output), readFileSync(path.join(root, source)));
  else if (old !== source) {
    const redirect = readFileSync(output.replace(/\.md$/, '.html'), 'utf8');
    assert(redirect.includes('location.search+location.hash'), `Legacy redirect loses fragments: ${old}`);
  }
}
for (const file of files(path.join(root, 'blogs')).filter(f => f.endsWith('.md'))) {
  const markdown = readFileSync(file, 'utf8').replace(/```[\s\S]*?```/g, '');
  for (const match of markdown.matchAll(/\]\(([^\s)]+)\)/g)) {
    const href = match[1];
    if (/^(?:https?:|mailto:|#)/.test(href)) continue;
    assert(existsSync(path.resolve(path.dirname(file), decodeURIComponent(href.split('#')[0]))), `Broken Markdown reference ${href} in ${file}`);
  }
}
for (const page of ['blogs/index.html', 'blogs/qwen3-tts-streaming/index.html', 'blogs/qwen3-tts-streaming/optimization.zh.html', 'blogs/qwen3-tts-streaming/optimization.en.html', 'blogs/qwen3-tts-streaming/repro/readme.html']) {
  const html = readFileSync(path.join(site, page), 'utf8');
  assert(/<article[\s>]/.test(html), `Missing article body: ${page}`);
  assert(!html.includes('<title>无题</title>'), `Missing page title: ${page}`);
}
assert(readFileSync(path.join(site, 'blogs/qwen3-tts-streaming/optimization.zh.html'), 'utf8').includes('CUDA Graph'));
assert(![...outputFiles].some(f => /(?:__pycache__|\.pyc$|\.env$|node_modules)/.test(f)), 'Published a local cache or environment file');
assert(existsSync(path.join(site, 'blogs/qwen3-tts-streaming/optimization.zh.html')));
assert(existsSync(path.join(site, 'blogs/qwen3-tts-streaming/optimization.en.html')));
assert(!files(site).some(f => f.includes('/.obsidian/')), 'Published Obsidian configuration');
assert(readFileSync(path.join(site, 'blogs/static/contentIndex.json'), 'utf8').includes('optimization.zh'), 'Missing article in search index');
console.log(`Verified ${references} HTML references, ${Object.keys(legacy).length} legacy files, Markdown links, and unchanged scripts/files.`);
