const {Buffer} = require('buffer');

const unsupported = () => {
  throw new Error('react-native-quick-crypto is native-only; use the device/native test suite for cryptographic integration tests.');
};

module.exports = {
  Buffer,
  randomBytes: unsupported,
  createCipheriv: unsupported,
  createDecipheriv: unsupported,
};
