/**
 * inject_ariang_hack.js
 *
 * Injeta hack de resiliencia no AriaNg (C:\AriaNg-Web\index.html).
 *
 * Estrategia (simples e robusta):
 * - Hack no <head>, ANTES do AngularJS bootstrapar
 * - Descobre a porta RPC via endpoint /rpc-port (mesma origem, sem CORS)
 * - Valida via proxy /jsonrpc-proxy (mesma origem, sem CORS)
 * - Atualiza rpcPort no localStorage via JSON.parse/stringify
 * - AriaNg conecta na porta certa na primeira vez
 * - Poll async a cada 10s; se daemon cair e voltar numa porta diferente,
 *   atualiza localStorage e recarrega (com anti-loop no sessionStorage)
 * - Badge de status com a porta descoberta
 * - SEM XHR cross-origin (tudo passa pelo proxy na mesma origem)
 *
 * Uso: node tools/inject_ariang_hack.js
 */
const fs = require('fs');
const file = 'C:\\AriaNg-Web\\index.html';
let html = fs.readFileSync(file, 'utf8');

// Remover hack antigo (qualquer versao)
if (html.includes('ariaNgResilience')) {
  console.log('Removendo hack antigo...');
  html = html.replace(/<!-- ariaNgResilience START -->[\s\S]*?<!-- ariaNgResilience END -->/, '');
}

const hack = `<!-- ariaNgResilience START -->
<script>
(function(){
  'use strict';

  var rpcPort = null;
  var connected = false;
  var reloadGuardKey = 'ariaNgResilience_reloaded_at';
  var OPTIONS_KEY = 'AriaNg.Options';

  function log(msg) {
    console.log('[ariaNgResilience] ' + msg);
  }

  /* === Badge de status === */
  var badge = document.createElement('div');
  badge.id = 'ariaNgResilienceBadge';
  badge.style.cssText = 'position:fixed;top:5px;right:5px;z-index:99999;padding:4px 12px;border-radius:4px;font-size:12px;font-family:monospace;font-weight:bold;color:#fff;transition:all 0.3s;pointer-events:none;box-shadow:0 2px 8px rgba(0,0,0,0.3);';
  badge.textContent = 'Iniciando...';
  badge.style.background = '#f39c12';

  function appendBadge() {
    if (document.body && !document.getElementById('ariaNgResilienceBadge')) {
      document.body.appendChild(badge);
    }
  }

  function setBadge(text, color) {
    badge.textContent = text;
    badge.style.background = color;
  }

  /* === Ler/atualizar porta no localStorage via JSON (robusto) === */
  function getConfiguredPort() {
    try {
      var raw = localStorage.getItem(OPTIONS_KEY);
      if (!raw) return null;
      var opts = JSON.parse(raw);
      return opts.rpcPort ? parseInt(opts.rpcPort) : null;
    } catch(e) { return null; }
  }

  function updateConfiguredPort(port) {
    try {
      var raw = localStorage.getItem(OPTIONS_KEY);
      var opts = raw ? JSON.parse(raw) : {};
      var oldPort = opts.rpcPort;
      opts.rpcPort = String(port);
      if (!opts.rpcHost || opts.rpcHost === 'localhost') opts.rpcHost = '127.0.0.1';
      if (!opts.protocol) opts.protocol = 'http';
      if (!opts.rpcInterface) opts.rpcInterface = 'jsonrpc';
      if (!opts.httpMethod) opts.httpMethod = 'POST';
      localStorage.setItem(OPTIONS_KEY, JSON.stringify(opts));
      if (String(oldPort) !== String(port)) {
        log('localStorage rpcPort: ' + oldPort + ' -> ' + port);
      }
      return true;
    } catch(e) { log('Erro atualizando localStorage: ' + e.message); return false; }
  }

  /* === Probe RPC via proxy (mesma origem, sem CORS) === */
  function probeRpcSync(port) {
    try {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', '/jsonrpc-proxy', false);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify({jsonrpc:'2.0',method:'aria2.getVersion',id:'probe',params:[]}));
      if (xhr.status === 200) {
        var data = JSON.parse(xhr.responseText);
        if (data.result && data.result.version) {
          return data.result.version;
        }
      }
    } catch(e) {}
    return null;
  }

  function probeRpcAsync(port, cb) {
    try {
      var xhr = new XMLHttpRequest();
      xhr.timeout = 5000;
      xhr.onload = function() {
        if (xhr.status === 200) {
          try {
            var data = JSON.parse(xhr.responseText);
            if (data.result && data.result.version) { cb(data.result.version); return; }
          } catch(e) {}
        }
        cb(null);
      };
      xhr.onerror = xhr.ontimeout = function() { cb(null); };
      xhr.open('POST', '/jsonrpc-proxy', true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify({jsonrpc:'2.0',method:'aria2.getVersion',id:'probe',params:[]}));
    } catch(e) { cb(null); }
  }

  /* === Descobrir porta RPC (sincrono, antes do AngularJS) ===
     Usa o endpoint /rpc-port do servidor web (ariang_web.js).
     O servidor descobre via netstat (PIDs de aria2c.exe em LISTENING).
     Validacao via proxy /jsonrpc-proxy (mesma origem, sem CORS). */
  function discoverPortSync() {
    // 1. Pergunta ao servidor web qual porta o aria2c esta ouvindo
    try {
      var xhr = new XMLHttpRequest();
      xhr.open('GET', '/rpc-port', false);
      xhr.send();
      if (xhr.status === 200) {
        var info = JSON.parse(xhr.responseText);
        if (info.port) {
          var port = parseInt(info.port);
          // Valida via proxy (mesma origem)
          var version = probeRpcSync(port);
          if (version) {
            log('Daemon encontrado na porta ' + port + ' (v' + version + ')');
            return port;
          }
        }
      }
    } catch(e) {}

    // 2. Fallback: porta configurada no localStorage
    var configured = getConfiguredPort();
    if (configured) {
      var version2 = probeRpcSync(configured);
      if (version2) {
        log('Daemon encontrado na porta ' + configured + ' via localStorage (v' + version2 + ')');
        return configured;
      }
    }

    log('Nenhuma porta respondendo');
    return null;
  }

  /* === Descobrir porta (async, para reconexao) === */
  function discoverPortAsync(cb) {
    // 1. Pergunta ao servidor web
    try {
      var xhr = new XMLHttpRequest();
      xhr.timeout = 3000;
      xhr.onload = function() {
        if (xhr.status === 200) {
          try {
            var info = JSON.parse(xhr.responseText);
            if (info.port) {
              var port = parseInt(info.port);
              probeRpcAsync(port, function(version) {
                if (version) { cb(port); return; }
                discoverPortAsyncFallback(cb);
              });
              return;
            }
          } catch(e) {}
        }
        discoverPortAsyncFallback(cb);
      };
      xhr.onerror = xhr.ontimeout = function() { discoverPortAsyncFallback(cb); };
      xhr.open('GET', '/rpc-port', true);
      xhr.send();
    } catch(e) { discoverPortAsyncFallback(cb); }
  }

  function discoverPortAsyncFallback(cb) {
    var configured = getConfiguredPort();
    if (!configured) { cb(null); return; }
    probeRpcAsync(configured, function(version) {
      if (version) { cb(configured); } else { cb(null); }
    });
  }

  /* === Verificar se daemon esta vivo (async) === */
  function checkAliveAsync(cb) {
    probeRpcAsync(rpcPort, function(version) {
      cb(!!version);
    });
  }

  /* === Inicializacao sincrona (antes do AngularJS) === */
  rpcPort = discoverPortSync();

  if (rpcPort) {
    updateConfiguredPort(rpcPort);
    connected = true;
    setBadge('RPC:' + rpcPort, '#27ae60');
  } else {
    setBadge('Sem daemon', '#e74c3c');
  }

  // Append badge quando body estiver disponivel
  if (document.body) {
    appendBadge();
  } else {
    document.addEventListener('DOMContentLoaded', appendBadge);
  }

  /* === Poll async: reconectar se daemon cair e voltar === */
  setInterval(function() {
    discoverPortAsync(function(newPort) {
      if (!newPort) {
        if (connected) {
          connected = false;
          setBadge('Desconectado', '#e74c3c');
        }
        return;
      }
      if (!connected || newPort !== rpcPort) {
        var oldPort = rpcPort;
        rpcPort = newPort;
        updateConfiguredPort(newPort);
        connected = true;
        setBadge('RPC:' + newPort, '#27ae60');
        if (oldPort && oldPort !== newPort) {
          log('Porta mudou: ' + oldPort + ' -> ' + newPort + '. Recarregando...');
          // Anti-loop: so recarrega uma vez por 10s
          var lastReload = sessionStorage.getItem(reloadGuardKey);
          var now = Date.now().toString();
          if (!lastReload || (parseInt(now) - parseInt(lastReload)) > 10000) {
            sessionStorage.setItem(reloadGuardKey, now);
            location.reload();
          }
        }
      } else {
        setBadge('RPC:' + rpcPort, '#27ae60');
      }
    });
  }, 10000);

  log('Hack inicializado. Porta: ' + rpcPort);
})();
</script>
<!-- ariaNgResilience END -->`;

// Inserir hack no <head>, antes de qualquer script do AriaNg
const headClose = html.indexOf('</head>');
if (headClose < 0) {
  console.error('</head> nao encontrado!');
  process.exit(1);
}
html = html.substring(0, headClose) + hack + html.substring(headClose);
fs.writeFileSync(file, html, 'utf8');
console.log('Hack injetado com sucesso em ' + file);
console.log('Tamanho do hack: ' + hack.length + ' bytes');
