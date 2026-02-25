const common = require('./webpack.common.js')
const { merge } = require('webpack-merge')
const TerserPlugin = require('terser-webpack-plugin')

module.exports = merge(common, {
  devtool: false,
  optimization: {
    minimize: true,
    minimizer: [
      new TerserPlugin({
        parallel: true,
        terserOptions: {
          ecma: 5,
          format: {
            comments: false
          }
        },
        extractComments: false
      })
    ],
    splitChunks: {
      chunks: 'all',
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
      },
    },
  }
})
