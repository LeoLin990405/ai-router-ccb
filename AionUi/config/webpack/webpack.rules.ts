import MiniCssExtractPlugin from 'mini-css-extract-plugin';
import path from 'path';
import type { ModuleOptions } from 'webpack';

export const rules: Required<ModuleOptions>['rules'] = [
  {
    test: /\.wasm$/,
    type: 'asset/resource',
    generator: {
      filename: 'wasm/[name][ext]',
    },
  },
  {
    test: /native_modules[/\\].+\.node$/,
    use: 'node-loader',
  },
  {
    test: /\.m?js/,
    resolve: {
      fullySpecified: false,
    },
  },
  {
    test: /[/\\]node_modules[/\\].+\.(m?js|node)$/,
    parser: { amd: false },
    exclude: /[/\\]node_modules[/\\](mermaid|streamdown|marked|shiki|@shikijs)[/\\]/,
    use: {
      loader: '@vercel/webpack-asset-relocator-loader',
      options: {
        outputAssetBase: 'native_modules',
      },
    },
  },
  {
    test: /\.tsx?$/,
    exclude: /(node_modules|\.webpack)/,
    use: {
      loader: 'ts-loader',
      options: {
        transpileOnly: true,
      },
    },
  },
  {
    test: /\.css$/,
    use: [
      MiniCssExtractPlugin.loader,
      {
        loader: 'css-loader',
        options: {
          importLoaders: 1,
        },
      },
      'postcss-loader',
    ],
    include: [/src/, /node_modules/],
  },
  {
    test: /_virtual_%2F__uno\.css$/,
    use: [MiniCssExtractPlugin.loader, 'css-loader'],
  },
  {
    test: /\.(woff|woff2|eot|ttf|otf)$/i,
    type: 'asset/resource',
    generator: {
      filename: 'static/fonts/[name][ext]',
    },
  },
  {
    test: /\.(png|jpe?g|gif|bmp|webp)$/i,
    type: 'asset/resource',
    generator: {
      filename: 'static/images/[name][ext]',
    },
  },
  {
    test: /\.json$/,
    type: 'json',
    parser: {
      parse: (source: string) => {
        try {
          return JSON.parse(source);
        } catch (e) {
          return {};
        }
      },
    },
  },
  {
    test: /\.svg$/,
    type: 'asset/resource',
    generator: {
      filename: 'static/images/[name][ext]',
    },
  },
  {
    test: /\.tsx$/,
    exclude: /node_modules/,
    use: [
      {
        loader: path.resolve(__dirname, './icon-park-loader.js'),
        options: {
          cacheDirectory: true,
          cacheIdentifier: 'icon-park-loader',
        },
      },
    ],
  },
];
