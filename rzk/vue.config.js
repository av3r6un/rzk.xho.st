const { defineConfig } = require('@vue/cli-service');
const webpack = require('webpack');

module.exports = defineConfig({
  transpileDependencies: true,
  css: {
    loaderOptions: {
      scss: {
        additionalData: '@import "@/assets/variables.scss";',
      },
    },
  },
  devServer: {
    port: 3000,
    allowedHosts: 'all',
    proxy: {
      '/auth/': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/api/': {
        target: 'http://localhost:8080/api/',
        changeOrigin: true,
        ws: true,
        pathRewrite: { '^/api': '' },
      },
    },
  },
  configureWebpack: {
    plugins: [
      new webpack.DefinePlugin({
        __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
      }),
    ],
  },
});
