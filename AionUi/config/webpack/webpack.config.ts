import type { Configuration } from 'webpack';
import { rules } from './webpack.rules';
import { plugins } from './webpack.plugins';
import { isDevelopment } from './helpers/paths';
import { createResolveConfig } from './helpers/resolve';
import path from 'path';

export const mainConfig: Configuration = {
  mode: isDevelopment ? 'development' : 'production',
   evtool: isDevelopment ? 'source-map' : false,
   ntry: {
    index: './src/index.ts',
    worker: './src/worker/index.ts',
    gemini: './src/worker/gemini.ts',
    acp: './src/worker/acp.ts',
    codex: './src/worker/codex.ts',
    'openclaw-gateway': './src/worker/openclaw-gateway.ts',
    hivemind: './src/worker/hivemind.ts',
  },
  output: {
    filename: '[name].js',
  },
  module: {
    rules,
  },
  plugins,
  resolve: {
    ...createResolveConfig(),
    alias: {
      ...createResolveConfig().alias,
      '@xterm/headless$': path.resolve(__dirname, '../../src/shims/xterm-headless.ts'),
    },
  },
  externals: {
    'better-sqlite3': 'commonjs better-sqlite3',
    'node-pty': 'commonjs node-pty',
    'playwright': 'commonjs playwright',
    'playwright-core': 'commonjs playwright-core',
    'tree-sitter': 'commonjs tree-sitter',
    'tree-sitter-bash': 'commonjs tree-sitter-bash',
    'web-tree-sitter': 'commonjs web-tree-sitter',
    'web-tree-sitter/tree-sitter.wasm?binary': 'commonjs web-tree-sitter/tree-sitter.wasm',
    'tree-sitter-bash/tree-sitter-bash.wasm?binary': 'commonjs tree-sitter-bash/tree-sitter-bash.wasm',
  },
};
