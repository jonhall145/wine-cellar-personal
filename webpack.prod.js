const common = require('./webpack.common.js')
const { merge } = require('webpack-merge')
const TerserPlugin = require('terser-webpack-plugin')
const { BundleAnalyzerPlugin } = require('webpack-bundle-analyzer')

const plugins = []

if (process.env.ANALYZE) {
  plugins.push(new BundleAnalyzerPlugin())
}

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
  },
  plugins,
})
