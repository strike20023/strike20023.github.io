import { execFileSync } from 'node:child_process';
import { cpSync, mkdirSync, rmSync, existsSync, writeFileSync, readFileSync, readdirSync, mkdtempSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { root, engine, site } from './paths.mjs';
import { addCompatibility, redirect } from './compat.mjs';
import { prepareLanguages, mergeLanguages } from './languages.mjs';

if (!existsSync(path.join(engine, 'node_modules'))) throw new Error('Run npm run setup first.');
cpSync(new URL('./quartz.config.yaml', import.meta.url), path.join(engine, 'quartz.config.yaml'));
const input = mkdtempSync(path.join(tmpdir(), 'zhe-quartz-'));
process.on('exit', () => rmSync(input, { recursive: true, force: true }));
rmSync(site, { recursive: true, force: true });
mkdirSync(input, { recursive: true });
function copyPublicFiles(prefix, destination, omit = []) {
  const entries = execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z', prefix], { cwd: root }).toString().split('\0').filter(Boolean);
  for (const file of new Set(entries)) {
    if (file.split('/').some(p => p.startsWith('.')) || omit.includes(file) || !existsSync(path.join(root, file))) continue;
    const output = path.join(destination, path.relative(prefix, file));
    mkdirSync(path.dirname(output), { recursive: true });
    cpSync(path.join(root, file), output);
  }
}
copyPublicFiles('blogs', input, ['blogs/README.md']);
const require = createRequire(path.join(engine, 'package.json'));
const YAML = require('yaml');
const { slug: slugHeading } = require('github-slugger');
function prepareMarkdown(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) { prepareMarkdown(file); continue; }
    if (!file.endsWith('.md')) continue;
    let text = readFileSync(file, 'utf8');
    const frontmatter = text.match(/^---\n([\s\S]*?)\n---\n/);
    const body = frontmatter ? text.slice(frontmatter[0].length) : text;
    const heading = body.match(/^\s*# ([^\n]+)\n/);
    if (!heading) continue;
    const title = heading[1].trim();
    const anchor = `<span id="${slugHeading(title)}"></span>\n`;
    if (!frontmatter) text = `---\ntitle: ${JSON.stringify(title)}\n---\n` + anchor + body.slice(heading[0].length);
    else if (YAML.parse(frontmatter[1]).title === title) text = frontmatter[0] + anchor + body.slice(heading[0].length);
    writeFileSync(file, text);
  }
}
const english = prepareLanguages(input);
prepareMarkdown(input);
execFileSync(process.execPath, ['quartz/bootstrap-cli.mjs', 'build', '-d', input, '-o', path.join(site, 'blogs'), '--concurrency=2'], { cwd: engine, stdio: 'inherit' });
// Preserve the source files used by direct downloads and scripts.
cpSync(input, path.join(site, 'blogs'), { recursive: true });
for (const dir of ['homepage', 'scripts', 'files']) copyPublicFiles(dir, path.join(site, dir));
cpSync(path.join(root, 'README.md'), path.join(site, 'README.md'));
writeFileSync(path.join(site, 'index.html'), redirect('homepage/'));
writeFileSync(path.join(site, 'README.html'), redirect('homepage/'));
writeFileSync(path.join(site, '.nojekyll'), '');
addCompatibility();
const englishOutput = mkdtempSync(path.join(tmpdir(), 'zhe-quartz-en-'));
process.on('exit', () => rmSync(englishOutput, { recursive: true, force: true }));
for (const [slug, text] of english) writeFileSync(path.join(input, `${slug}.md`), text);
prepareMarkdown(input);
execFileSync(process.execPath, ['quartz/bootstrap-cli.mjs', 'build', '-d', input, '-o', englishOutput, '--concurrency=2'], { cwd: engine, stdio: 'inherit' });
mergeLanguages(path.join(site, 'blogs'), englishOutput);
console.log(`Built ${site}`);
