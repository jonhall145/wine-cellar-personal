const path = require('path')
const CopyWebpackPlugin = require('copy-webpack-plugin')
const MiniCssExtractPlugin = require('mini-css-extract-plugin')

module.exports = {
  entry: {
    base: {
      import: [
        './wine_cellar/assets/css/menu.css',
        './wine_cellar/assets/css/detail.css',
        './wine_cellar/assets/css/storage.css',
        './wine_cellar/assets/css/utility.css',
        './wine_cellar/assets/css/card.css',
        './wine_cellar/assets/css/forms.css',
        './wine_cellar/assets/css/styles.css',
        './wine_cellar/assets/css/page-layout.css',
        './wine_cellar/assets/css/homepage.css',
        './wine_cellar/assets/css/button.css',
        './node_modules/tom-select/dist/css/tom-select.css',
        './node_modules/@fortawesome/fontawesome-free/css/fontawesome.css',
        './node_modules/@fortawesome/fontawesome-free/css/solid.css',
        './wine_cellar/assets/js/theme_toggle.ts',
        './wine_cellar/assets/js/form_loading.ts',
        './wine_cellar/assets/js/dropdown_toggle.ts',
      ],
    },
    storage_view_toggle: {
      import: ['./wine_cellar/assets/js/storage_view_toggle.ts'],
    },
    tom_select: {
      import: ['./wine_cellar/assets/js/init_tom_select.ts'],
    },
    stock_add: {
      import: ['./wine_cellar/assets/js/stock_add.ts'],
    },
    barcode_scanner: {
      import: ['./wine_cellar/react/react_bar_code.tsx'],
    },
    label_scanner: {
      import: ['./wine_cellar/react/react_label_scanner.tsx'],
    },
    maps: {
      import: [
        'leaflet/dist/leaflet.css',
        'maplibre-gl/dist/maplibre-gl.css',
        'leaflet.markercluster/dist/MarkerCluster.css',
        './wine_cellar/assets/css/map.css',
        './wine_cellar/react/maps/react_maps.tsx'
      ]
    },
    distillery_map: {
      import: [
        'leaflet/dist/leaflet.css',
        'leaflet.markercluster/dist/MarkerCluster.css',
        './wine_cellar/assets/css/map.css',
        './wine_cellar/react/maps/react_distillery_map.tsx'
      ]
    },
    wine_carousel: {
      import: ['./wine_cellar/assets/js/wine_carousel.ts'],
    },
    image_preview: {
      import: ['./wine_cellar/assets/js/image_preview.ts'],
    },
    vision_extraction: {
      import: ['./wine_cellar/assets/js/vision_extraction.js'],
    },
    whisky_vision_extraction: {
      import: ['./wine_cellar/assets/js/whisky_vision_extraction.js'],
    },
    storage_grid: {
      import: ['./wine_cellar/react/storage_grid.tsx'],
    },
    mask_editor: {
      import: ['./wine_cellar/assets/js/mask_editor.ts'],
    }
  },
  output: {
    path: path.resolve('./wine_cellar/static/'),
    publicPath: '/static/',
  },
  externals: {
    django: 'django',
  },
  cache: {
    type: 'filesystem',
    buildDependencies: {
      config: [__filename],
    },
  },
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        exclude: /node_modules\/.*/, // exclude most dependencies
        loader: 'babel-loader',
        options: {
          cacheDirectory: true,
          presets: ['@babel/preset-env', '@babel/preset-react'].map(
            require.resolve
          ),
          plugins: [
            '@babel/plugin-transform-runtime',
            '@babel/plugin-transform-modules-commonjs',
          ],
        },
      },
      {
        test: /\.tsx?$/,
        use: {
          loader: 'ts-loader',
          options: {
            transpileOnly: true,
          },
        },
        exclude: /node_modules/,
      },
      {
        test: /\.s?css$/,
        use: [
          {
            loader: MiniCssExtractPlugin.loader,
          },
          {
            loader: 'css-loader',
            options: {
              url: {
                filter: (url, resourcePath) => {
                  // only handle `/` urls, leave rest in code (pythong images to be left)
                  if (!url.startsWith('/')) {
                    return true
                  } else {
                    return false
                  }
                },
              },
            },
          },
          {
            loader: 'postcss-loader',
            options: {
              postcssOptions: {
                plugins: [require('autoprefixer')],
              },
            },
          },
        ],
      },
      {
        test: /fonts\/.*\.(svg|woff2?|ttf|eot)(\?.*)?$/,
        type: 'asset/resource',
        generator: {
          filename: 'fonts/[name][ext]',
        },
      },
      {
        test: /\.svg$|\.png$/,
        type: 'asset/resource',
        generator: {
          filename: 'images/[name][ext]',
        },
      },
    ],
  },
  resolve: {
    fallback: {
      path: require.resolve('path-browserify'),
      url: require.resolve('url/'),
    },
    extensions: ['*', '.js', '.jsx', '.scss', '.css', '.ts', '.tsx'],
    alias: {},
    // when using `npm link`, dependencies are resolved against the linked
    // folder by default. This may result in dependencies being included twice.
    // Setting `resolve.root` forces webpack to resolve all dependencies
    // against the local directory.
    modules: [path.resolve('./node_modules')],
  },
  optimization: {
    splitChunks: {
      chunks: 'async',
      cacheGroups: {
        reactVendor: {
          test: /[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/,
          name: 'react-vendors',
          chunks: 'all',
          priority: 20,
        },
        leafletVendor: {
          test: /[\\/]node_modules[\\/](leaflet|maplibre-gl|@maplibre|leaflet\.markercluster)[\\/]/,
          name: 'leaflet-vendors',
          chunks: 'all',
          priority: 20,
        },
        faVendor: {
          test: /[\\/]node_modules[\\/]@fortawesome[\\/]/,
          name: 'fontawesome-vendors',
          chunks: 'all',
          priority: 30,
          enforce: true,
        },
      },
    },
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: '[name].css',
      chunkFilename: '[name].css',
    }),
    new CopyWebpackPlugin({
      patterns: [
        {
          from: './wine_cellar/assets/images/**/*',
          to: 'images/[name][ext]',
        },
        {
          from: './wine_cellar/assets/js/index.js.map',
          to: '[name][ext]',
        },
        {
          from: './node_modules/tom-select/dist/css/tom-select.css.map',
          to: '[name][ext]',
        },
        {
          from: './node_modules/zxing-wasm/dist/reader/zxing_reader.wasm',
          to: '[name][ext]',
        },
        {
          from: './node_modules/leaflet/dist/*.map',
          to: '[name][ext]',
        },
        {
          from: './node_modules/leaflet.markercluster/dist/*.map',
          to: '[name][ext]',
        },
        {
          from: './wine_cellar/react/maps/country.json',
          to: 'maps/[name][ext]',
        },
        {
          from: './wine_cellar/react/maps/countries-boundaries.json',
          to: 'maps/[name][ext]',
        },
      ],
    }),
  ],
}
