import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/cli.ts'],
  format: ['esm'],
  outDir: 'dist',
  clean: true,
  sourcemap: false,
  external: [
    /^node:/,
    'readline',
    'readline/promises',
    'fs',
    'path',
    'os',
    'child_process',
    'crypto',
    'util',
    'stream',
    'buffer',
    'events',
  ],
  target: 'node20',
  platform: 'node',
});

