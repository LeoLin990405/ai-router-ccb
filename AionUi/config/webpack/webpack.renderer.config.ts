import path from 'path';
import type { Configuration } from 'webpack';
import webpack from 'webpack';
import { plugins } from './webpack.plugins';
import { rules } from './webpack.rules';
import { isDevelopment } from './helpers/paths';
import { createResolveConfig } from './helpers/resolve';

export const rendererConfig: Configuration = {
  mode: isDevelopment ? 'development' : 'production',
  devtool: isDevelopment ? 'source-map' : false,
  module: {
    rules,
  },
  plugins: [
    ...plugins,
    new webpack.ProvidePlugin({
      Buffer: ['buffer', 'Buffer'],
      process: 'process/browser',
    }),
  ],
  resolve: {
    ...createResolveConfig(['.css']),
    alias: {
      ...createResolveConfig(['.css']).alias,
      'process/browser': require.resolve('process/browser.js'),
      'streamdown': path.resolve(__dirname, '../../node_modules/streamdown/dist/index.js'),
    },
    fallback: {
      'crypto': false,
      'node:crypto': false,
      'stream': require.resolve('stream-browserify'),
      'buffer': require.resolve('buffer'),
      'process': require.resolve('process/browser.js'),
      'process/browser': require.resolve('process/browser.js'),
      'zlib': false,
      'util': false,
    },
  },
  externals: {
    'node:crypto': 'commonjs2 crypto',
    'crypto': 'commonjs2 crypto',
  },
  optimization: {
    realContentHash: true,
    minimize: !isDevelopment,
    splitChunks: isDevelopment ? false : {
      chunks: 'all',
      maxInitialRequests: 25,
      minSize: 20000,
      cacheGroups: {
        react: {
          test: /[\\/]node_modules[\\/](react|react-dom|react-router-dom)[\\/]/,
          name: 'react',
          priority: 30,
        },
        arco: {
          test: /[\\/]node_modules[\\/]@arco-design[\\/]/,
          name: 'arco',
          priority: 25,
        },
        markdown: {
          test: /[\\/]node_modules[\\/](react-markdown|react-syntax-highlighter|katex|rehype-katex|remark-)[\\/]/,
          name: 'markdown',
          priority: 20,
        },
        codemirror: {
          test: /[\\/]node_modules[\\/](@uiw|@codemirror)[\\/]/,
          name: 'codemirror',
          priority: 20,
        },
        vendors: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          priority: 10,
        },
      },
    },
  },
};
