import { execFileSync } from 'node:child_process';
import { mkdirSync, existsSync, readFileSync, writeFileSync, cpSync, rmSync } from 'node:fs';
import path from 'node:path';

import { root, engine } from './paths.mjs';
const { commit } = JSON.parse(readFileSync(new URL('./upstream.json', import.meta.url)));
const marker = path.join(engine, '.site-revision');
if (!existsSync(marker) || readFileSync(marker, 'utf8').trim() !== commit) {
  mkdirSync(path.join(root, '.cache'), { recursive: true });
  rmSync(engine, { recursive: true, force: true });
  mkdirSync(engine, { recursive: true });
  const git = (...args) => execFileSync('git', args, { cwd: engine, stdio: 'inherit' });
  git('init');
  git('remote', 'add', 'origin', 'https://github.com/jackyzha0/quartz.git');
  git('config', 'remote.origin.promisor', 'true');
  git('config', 'remote.origin.partialclonefilter', 'blob:none');
  git('sparse-checkout', 'init', '--cone');
  git('sparse-checkout', 'set', 'quartz');
  git('fetch', '--depth=1', '--filter=blob:none', 'origin', commit);
  git('checkout', '--detach', 'FETCH_HEAD');
  writeFileSync(marker, `${commit}\n`);
}
cpSync(new URL('./quartz.config.yaml', import.meta.url), path.join(engine, 'quartz.config.yaml'));
execFileSync('npm', ['ci', '--no-audit', '--no-fund'], { cwd: engine, stdio: 'inherit' });
execFileSync(process.execPath, ['quartz/bootstrap-cli.mjs', 'plugin', 'install', '--from-config'], { cwd: engine, stdio: 'inherit' });
