import { fileURLToPath } from 'node:url';
import path from 'node:path';
export const root = fileURLToPath(new URL('../../', import.meta.url));
export const engine = path.join(root, '.cache/quartz');
export const site = path.join(root, '.site');
