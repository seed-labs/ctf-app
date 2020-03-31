let config = {
  api: {
    protocol: 'http',
    host: '192.168.1.234',
    port: 5000,
    prefix: 'api'
  },
};

config.endpoint = config.api.protocol + '://' +
  config.api.host + ':' +
  config.api.port + '/' +
  config.api.prefix + '/';

module.exports = config;