const { createProxyMiddleware } = require('http-proxy-middleware');

// Порт бэкенда берётся из переменной окружения, которую передаёт run.py
// (или можно использовать значение по умолчанию 8000)
const BACKEND_PORT = process.env.BACKEND_PORT || '8000';
const TARGET = `http://localhost:${BACKEND_PORT}`;

module.exports = function (app) {
  const apiProxy = createProxyMiddleware({
    target: TARGET,
    changeOrigin: true,
    onProxyRes: (proxyRes) => {
      proxyRes.headers['X-Accel-Buffering'] = 'no';
      proxyRes.headers['Cache-Control'] = 'no-cache';
      proxyRes.headers['Connection'] = 'keep-alive';
    },
  });

  app.use('/action/stream', apiProxy);
  app.use('/action', apiProxy);
  app.use('/saves', apiProxy);
  app.use('/world', apiProxy);
  app.use('/memory', apiProxy);
};