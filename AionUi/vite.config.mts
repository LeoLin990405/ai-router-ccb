/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Vite configuration for browser mode development and build
 */

import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import UnoCSS from 'unocss/vite';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [
      react(),
      UnoCSS(),
    ],

    // Path aliases (match webpack config)
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@renderer': path.resolve(__dirname, './src/renderer'),
        '@process': path.resolve(__dirname, './src/process'),
        '@worker': path.resolve(__dirname, './src/worker'),
        '@common': path.resolve(__dirname, './src/common'),
      },
    },

    // Development server configuration
    server: {
      port: parseInt(env.VITE_DEV_PORT || '3000', 10),
      host: env.VITE_DEV_HOST || 'localhost',

      // Proxy API requests to backend server
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL || 'http://localhost:8765',
          changeOrigin: true,
          secure: false,
          ws: true, // Enable WebSocket proxy
        },
        // WebSocket endpoint
        '/socket.io': {
          target: env.VITE_API_BASE_URL || 'http://localhost:8765',
          changeOrigin: true,
          secure: false,
          ws: true,
        },
      },

      // CORS configuration for development
      cors: true,

      // Enable HMR
      hmr: {
        overlay: true,
      },
    },

    // Build configuration
    build: {
      outDir: 'dist/web',
      sourcemap: mode === 'development',
      minify: mode === 'production' ? 'esbuild' : false,

      // Chunk splitting for better caching
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            'ui-vendor': ['@arco-design/web-react'],
            'editor-vendor': ['@monaco-editor/react', '@uiw/react-codemirror'],
            'ai-vendor': ['@anthropic-ai/sdk', '@google/genai', 'openai'],
          },
        },
      },

      // Target modern browsers
      target: 'es2020',
    },

    // Optimize dependencies
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-router-dom',
        '@arco-design/web-react',
        'axios',
        'socket.io-client',
      ],
      exclude: [
        // Exclude Electron-specific modules
        'electron',
        'better-sqlite3',
      ],
    },

    // Environment variables prefix
    envPrefix: 'VITE_',

    // Define global constants
    define: {
      __IS_ELECTRON__: false,
      __IS_DEV__: mode === 'development',
    },

    // CSS configuration
    css: {
      modules: {
        localsConvention: 'camelCase',
      },
    },
  };
});
