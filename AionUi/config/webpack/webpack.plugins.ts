import UnoCSS from '@unocss/webpack';
import CopyPlugin from 'copy-webpack-plugin';
import type IForkTsCheckerWebpackPlugin from 'fork-ts-checker-webpack-plugin';
import MiniCssExtractPlugin from 'mini-css-extract-plugin';
import path from 'path';
import type { WebpackPluginInstance } from 'webpack';
import webpack from 'webpack';
import unoConfig from '../../uno.config';

const ForkTsCheckerWebpackPlugin: typeof IForkTsCheckerWebpackPlugin = require('fork-ts-checker-webpack-plugin');

export const plugins: WebpackPluginInstance[] = [
  new CopyPlugin({
    patterns: [
      { from: path.resolve(__dirname, '../../skills'), to: 'skills', noErrorOnMissing: true },
      { from: path.resolve(__dirname, '../../rules'), to: 'rules', noErrorOnMissing: true },
      { from: path.resolve(__dirname, '../../assistant'), to: 'assistant', noErrorOnMissing: true },
      { from: path.resolve(__dirname, '../../src/renderer/assets/logos'), to: 'static/images', noErrorOnMissing: true, force: true },
    ],
  }),
  new ForkTsCheckerWebpackPlugin({
    logger: 'webpack-infrastructure',
  }),
  new webpack.DefinePlugin({
    'process.env.env': JSON.stringify(process.env.env),
  }),
  new MiniCssExtractPlugin({
    filename: '[name].css',
    chunkFilename: '[id].css',
  }),
  {
    apply(compiler) {
      if (compiler.options.name?.startsWith('HtmlWebpackPlugin')) {
        return;
      }
      UnoCSS(unoConfig).apply(compiler);
    },
  },
  new webpack.IgnorePlugin({
    resourceRegExp: /\.wasm\?binary$/,
  }),
];
