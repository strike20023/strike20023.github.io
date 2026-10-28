import { readFileSync, writeFileSync, mkdirSync, cpSync } from 'node:fs';
import path from 'node:path';
import { root, site } from './paths.mjs';

export const legacy = JSON.parse(readFileSync(new URL('./legacy-paths.json', import.meta.url)));
export function redirect(target) {
  const escaped = target.replaceAll('&', '&amp;').replaceAll('"', '&quot;');
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=${escaped}"><link rel="canonical" href="${escaped}"><title>Redirect</title><script>location.replace(${JSON.stringify(target)}+location.search+location.hash)</script></head><body><a href="${escaped}">Continue</a></body></html>\n`;
}
export function addCompatibility() {
  for (const [old, source] of Object.entries(legacy)) {
    const dest = path.join(site, old);
    mkdirSync(path.dirname(dest), { recursive: true });
    if (!source.endsWith('.md')) {
      cpSync(path.join(root, source), dest);
      continue;
    }
    let text = readFileSync(path.join(root, source), 'utf8');
    text = text.replace(/^---\n[\s\S]*?\n---\n\n/, '');
    if (old.includes('2026-10-21-')) {
      text = text.replaceAll('(repro/', '(qwen3-tts-streaming-repro/');
      for (const lang of ['zh', 'en']) text = text.replaceAll(`(optimization.${lang}.md)`, `(2026-10-21-qwen3-tts-streaming-optimization.${lang}.md)`);
    } else if (old.includes('/qwen3-tts-streaming-repro/')) {
      for (const lang of ['zh', 'en']) text = text.replaceAll(`(../optimization.${lang}.md)`, `(../2026-10-21-qwen3-tts-streaming-optimization.${lang}.md)`);
    }
    writeFileSync(dest, text);
    if (old !== source || old === 'blogs/README.md') {
      const htmlDest = dest.replace(/\.md$/, '.html');
      const htmlSource = old === 'blogs/README.md' ? 'blogs/index.html' : source.replace(/\.md$/, '.html').replace(/\/README\.html$/, '/readme.html');
      const relative = path.relative(path.dirname(htmlDest), path.join(site, htmlSource)).split(path.sep).join('/');
      writeFileSync(htmlDest, redirect(relative));
    }
  }
}
