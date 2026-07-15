const Database = require('better-sqlite3');
const fs = require('fs');

const cookiesPath = 'C:\\Users\\Usuario\\AppData\\Local\\ms-playwright-mcp\\mcp-chrome-ea75b46\\Default\\Network\\Cookies';

// Copiar o arquivo (Chrome pode ter lock)
const tmpPath = 'F:\\importre\\tools\\Cookies_copy.db';
fs.copyFileSync(cookiesPath, tmpPath);

const db = new Database(tmpPath, { readonly: true });

// Listar tabelas
const tables = db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all();
console.log('Tabelas:', tables.map(t => t.name).join(', '));

// Listar cookies do archive.org
const rows = db.prepare("SELECT host_key, name, value, encrypted_value, path, is_httponly, expires_utc FROM cookies WHERE host_key LIKE '%archive.org%'").all();
console.log(`\nCookies do archive.org: ${rows.length}`);

for (const row of rows) {
  const encrypted = row.encrypted_value && row.encrypted_value.length > 0;
  console.log(`  ${row.host_key} ${row.name}=${row.value ? row.value.substring(0, 60) : '[encrypted ' + (row.encrypted_value ? row.encrypted_value.length : 0) + ' bytes]'} httpOnly=${row.is_httponly} expires=${row.expires_utc}`);
}

db.close();
