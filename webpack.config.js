const path = require("path");

const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin");
const TerserPlugin = require("terser-webpack-plugin");
const BrowserSyncPlugin = require("browser-sync-webpack-plugin");

const BASE_DIR = __dirname;

module.exports = {
  entry: {
    base: "./status/static_src/index.js",
    pages: "./pages/static_src/index.js",
    properties: "./properties/static_src/index.js",
  },
  output: {
    path: path.resolve(BASE_DIR, "status/static"),
    filename: "[name].js",
  },
  optimization: {
    minimize: true,
    minimizer: [
      new CssMinimizerPlugin(),
      new TerserPlugin(),
    ],
  },
  plugins: [
    new BrowserSyncPlugin({
      proxy: "http://localhost:8000",
      files: [
        "status/static",
        "**/*.html",
        // "**/*.py",  // NOTE: enabling this causes us to up the reload delay to 2000ms which is not an enjoyable experience
      ],
      ignore: [
        "node_modules",
        "migrations",
        "media",
      ],
      notify: false,
      open: false,
      reloadDelay: 500,
      reloadDebounce: 1000,
    }),
    new MiniCssExtractPlugin({
      filename: "[name].css",
    }),
  ],
  module: {
    rules: [
      // Extract all CSS into their own files
      {
        test: /\.css$/,
        use: [MiniCssExtractPlugin.loader, "css-loader"],
      },
      {
        test: /\.scss$/,
        use: [MiniCssExtractPlugin.loader, "css-loader", "sass-loader"],
      },
      // Copy all images to the build directory
      {
        test: /\.(png|jpg|gif|svg|webp)$/,
        use: [
          {
            loader: "file-loader",
            options: {
              name: "[name].[ext]",
              outputPath: "images/",
            },
          },
        ],
      },
    ],
  },
};
