const fs = require('fs');
const path = require('path');
const { LOG_PATH } = require('./config');

class Logger {
  constructor(name) {
    this.name = name;
    this.stream = fs.createWriteStream(LOG_PATH, { flags: 'a' });
    this.stream.on('error', () => {});
  }

  log(level, msg) {
    try {
      const line = `[${new Date().toISOString()}] [${level}] [${this.name}] ${msg}`;
      console.log(line);
      this.stream.write(line + '\n');
    } catch (e) { /* ignore */ }
  }

  info(msg) { this.log('INFO', msg); }
  warn(msg) { this.log('WARN', msg); }
  error(msg) { this.log('ERROR', msg); }
}

module.exports = Logger;
