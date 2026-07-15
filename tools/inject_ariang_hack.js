/**
 * inject_ariang_hack.js
 *
 * Injeta hack de resiliencia no AriaNg (C:\AriaNg-Web\index.html).
 *
 * Estrategia (simples e robusta):
 * - Hack no <head>, ANTES do AngularJS bootstrapar
 * - Descobre a porta RPC sincronamente (XHR sync) antes do AriaNg ler o localStorage
 * - Atualiza rpcPort no localStorage via JSON.parse/stringify (nao regex)
 * - AriaNg conecta na porta certa na primeira vez
 * - Poll async a cada 10s; se daemon cair e voltar numa porta diferente,
 *   atualiza localStorage e recarrega (com anti-loop no sessionStorage)
 * - Badge de status com a porta descoberta
 * - SEM patches de XHR/fetch do AriaNg (zero interferencia)
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
  // O servidor web (ariang_web.js) descobre a porta via netstat e expoe em /rpc-port
  // Nenhuma lista hardcoded — a porta vem do sistema operacional.

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
      if (!raw) return false;
      var opts = JSON.parse(raw);
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

  /* === Descobrir porta RPC (sincrono, antes do AngularJS) ===
     Busca do endpoint /rpc-port do servidor web (ariang_web.js).
     O servidor descobre via netstat (PIDs de aria2c.exe em LISTENING).
     Fallback: porta configurada no localStorage. */
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
          // Valida com probe RPC
          try {
            var xhr2 = new XMLHttpRequest();
            xhr2.open('POST', 'http://127.0.0.1:' + port + '/jsonrpc', false);
            xhr2.setRequestHeader('Content-Type', 'application/json');
            xhr2.send(JSON.stringify({jsonrpc:'2.0',method:'aria2.getVersion',id:'probe',params:[]}));
            if (xhr2.status === 200) {
              var data = JSON.parse(xhr2.responseText);
              if (data.result && data.result.version) {
                log('Daemon encontrado na porta ' + port + ' via /rpc-port (v' + data.result.version + ')');
                return port;
              }
            }
          } catch(e) {}
        }
      }
    } catch(e) {}

    // 2. Fallback: porta configurada no localStorage
    var configured = getConfiguredPort();
    if (configured) {
      try {
        var xhr3 = new XMLHttpRequest();
        xhr3.open('POST', 'http://127.0.0.1:' + configured + '/jsonrpc', false);
        xhr3.setRequestHeader('Content-Type', 'application/json');
        xhr3.send(JSON.stringify({jsonrpc:'2.0',method:'aria2.getVersion',id:'probe',params:[]}));
        if (xhr3.status === 200) {
          var data2 = JSON.parse(xhr3.responseText);
          if (data2.result && data2.result.version) {
            log('Daemon encontrado na porta ' + configured + ' via localStorage');
            return configured;
          }
        }
      } catch(e) {}
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
              // Valida com probe RPC
              var xhr2 = new XMLHttpRequest();
              xhr2.timeout = 3000;
              xhr2.onload = function() {
                if (xhr2.status === 200) {
                  try {
                    var data = JSON.parse(xhr2.responseText);
                    if (data.result && data.result.version) { cb(port); return; }
                  } catch(e) {}
                }
                // Fallback localStorage
                discoverPortAsyncFallback(cb);
              };
              xhr2.onerror = xhr2.ontimeout = function() { discoverPortAsyncFallback(cb); };
              xhr2.open('POST', 'http://127.0.0.1:' + port + '/jsonrpc', true);
              xhr2.setRequestHeader('Content-Type', 'application/json');
              xhr2.send(JSON.stringify({jsonrpc:'2.0',method:'aria2.getVersion',id:'probe',params:[]}));
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
    try {
      var xhr = new XMLHttpRequest();
      xhr.timeout = 3000;
      xhr.onload = function() {
        if (xhr.status === 200) {
          try {
            var data = JSON.parse(xhr.responseText);
            if (data.result && data.result.version) { cb(configured); return; }
          } catch(e) {}
        }
        cb(null);
      };
      xhr.onerror = xhr.ontimeout = function() { cb(null); };
      xhr.open('POST', 'http://127.0.0.1:' + configured + '/jsonrpc', true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify({jsonrpc:'2.0',method:'aria2.getVersion',id:'probe',params:[]}));
    } catch(e) { cb(null); }
  }

  /* === Verificar se daemon esta vivo (async) === */
  function checkAliveAsync(cb) {
    if (!rpcPort) { cb(false); return; }
    try {
      var xhr = new XMLHttpRequest();
      xhr.timeout = 5000;
      xhr.onload = function() {
        try {
          var data = JSON.parse(xhr.responseText);
          cb(!!(data.result && data.result.version));
        } catch(e) { cb(false); }
      };
      xhr.onerror = xhr.ontimeout = function() { cb(false); };
      xhr.open('POST', 'http://127.0.0.1:' + rpcPort + '/jsonrpc', true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify({jsonrpc:'2.0',method:'aria2.getVersion',id:'alive',params:[]}));
    } catch(e) { cb(false); }
  }

  /* === Recarregar pagina com flag anti-loop === */
  function safeReload(reason) {
    try {
      var last = parseInt(sessionStorage.getItem(reloadGuardKey) || '0');
      var now = Date.now();
      if (now - last < 15000) {
        log('Reload bloqueado (anti-loop): ultimo ha ' + (now - last) + 'ms. Razao: ' + reason);
        setBadge('Conectado :' + rpcPort + ' (reload bloqueado)', '#27ae60');
        connected = true;
        return;
      }
      sessionStorage.setItem(reloadGuardKey, String(now));
      log('Recarregando pagina: ' + reason);
      location.reload();
    } catch(e) { log('Erro no reload: ' + e.message); }
  }

  /* === Loop de monitoramento (async, apos inicializacao) === */
  function poll() {
    checkAliveAsync(function(alive) {
      if (alive) {
        if (!connected) {
          connected = true;
          setBadge('Conectado :' + rpcPort, '#27ae60');
          log('Daemon conectado na porta ' + rpcPort);
        }
        setTimeout(poll, 10000);
      } else {
        connected = false;
        setBadge('Desconectado - buscando...', '#e74c3c');
        log('Daemon caiu na porta ' + rpcPort + '. Buscando...');
        discoverPortAsync(function(port) {
          if (port && port !== rpcPort) {
            log('Daemon voltou na porta ' + port + ' (era ' + rpcPort + ')');
            rpcPort = port;
            updateConfiguredPort(port);
            setBadge('Encontrado :' + port + ' - recarregando...', '#e67e22');
            safeReload('daemon voltou na porta ' + port);
            return;
          }
          if (port && port === rpcPort) {
            connected = true;
            setBadge('Conectado :' + port, '#27ae60');
            log('Daemon voltou na mesma porta ' + port);
            setTimeout(poll, 10000);
            return;
          }
          setBadge('Procurando daemon...', '#e74c3c');
          setTimeout(poll, 5000);
        });
      }
    });
  }

  /* === INICIALIZACAO SINCRONA (roda antes do AngularJS) === */
  var discoveredPort = discoverPortSync();
  if (discoveredPort) {
    rpcPort = discoveredPort;
    connected = true;
    var configured = getConfiguredPort();
    if (configured !== discoveredPort) {
      log('Porta configurada (' + configured + ') != descoberta (' + discoveredPort + '). Atualizando localStorage...');
      updateConfiguredPort(discoveredPort);
    }
    log('Hack inicializado - daemon na porta ' + discoveredPort);
  } else {
    log('Daemon nao encontrado na inicializacao.');
  }

  /* === Badge + poll async apos DOM ready === */
  function startAsync() {
    appendBadge();
    if (discoveredPort) {
      setBadge('Conectado :' + rpcPort, '#27ae60');
    } else {
      setBadge('Daemon offline', '#e74c3c');
    }
    setTimeout(poll, 10000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startAsync);
  } else {
    startAsync();
  }

  window.ariaNgResilience = {
    getPort: function() { return rpcPort; },
    isConnected: function() { return connected; },
    rediscover: function() { discoverPortAsync(function(p) { if (p) { rpcPort = p; updateConfiguredPort(p); } }); }
  };

  log('Hack carregado (head, pre-AngularJS) - porta: ' + discoveredPort);
})();
</script>
<!-- ariaNgResilience END -->`;

// Injetar no <head>, ANTES do AngularJS bootstrapar
html = html.replace('</head>', hack + '</head>');
fs.writeFileSync(file, html, 'utf8');
console.log('Hack injetado no <head> de', file);
console.log('Estrategia: JSON.parse/stringify + descoberta sincrona pre-AngularJS');
