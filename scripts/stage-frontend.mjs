import { cpSync, rmSync } from 'node:fs';
// Sites accepts a root-level static build directory. Only generated assets are staged.
rmSync(new URL('../dist/', import.meta.url), { recursive: true, force: true });
cpSync(new URL('../frontend/dist/', import.meta.url), new URL('../dist/', import.meta.url), { recursive: true });
