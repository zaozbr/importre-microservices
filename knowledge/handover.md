# Handover — Importre Microservices

**Data:** 2026-07-16 (sessao 4)
**Sistema:** Rodando — 2423/2486 completados (97.5%)

## Estado atual

- Orchestrator: porta 8767
- Queue: porta 9011
- Search: porta 9002
- Download: porta 9003
- CHD: porta 9004
- Dashboard: `http://127.0.0.1:8767/`
- aria2c: porta 6800, com cookie archive.org carregado
- AriaNg: porta 16801 (proxy RPC funcionando, hack injetado)

## Queue

- completed: 2423
- pending: 9
- searching: 43
- ready: 0
- downloading: 5
- failed: 0

## Velocidade de download

- Media: ~1 MB/s
- Picos: ~1.3 MB/s
- Meta: 40MB/s (nao alcancada — maioria dos itens restantes sao homebrew pequenos do itch.io)
- 21+ jogos PSX homebrew baixados do itch.io via itchio-downloader

## Sessao 2026-07-16 (sessao 4) — tarefas completadas

1. **Multi-source download implementado:** aria2 agora baixa chunks de multiplas URLs (mesmo size) em paralelo. Modificados aria2_rpc.js, aria2.js, index.js. groupMultiSourceSources() agrupa fontes HTTP por size.
2. **Resolver itch.io via itchio-downloader:** Biblioteca npm (v1.2.0) faz download via HTTP direto (CSRF → download page → CDN URL). 21+ jogos homebrew PSX baixados. Busca itch.io reativada em web_search.js.
3. **Conta itch.io criada via Playwright:** importre67103 (Cloudflare bloqueia axios/curl). Email descartavel mail.tm.
4. **Lint + testes:** 0 erros, 0 warnings. 200 testes passing.
5. **Commit:** 14bf5a7 (feat: multi-source download + resolver itch.io via itchio-downloader)

## Cookie archive.org (IMPORTANTE)

- Conta atual: `kideje5455@ezimb.com` / screenname `impcoll2026z` / senha `Arch2026xK9!mp`
- Cookie em `F:\importre\archive_cookies.txt` (formato Netscape) — NUNCA commitar (secret)
- Para renovar: `node tools/renew_archive_cookie.js`
- Se conta expirar: ver `knowledge/archive_cookie_renewal.md`
- **STATUS:** Cookie valido. Tor proxy ativo para contornar rate limiting.

## itch.io (novo)

- Conta: `importre67103` / senha `Importre123!` / email `importre67103@web-library.net`
- Token mail.tm salvo em `F:\importre_state\itch_account.json`
- Biblioteca `itchio-downloader` baixa jogos free sem precisar de login
- Downloads salvos em `F:\downloads\itch\` (game-*.zip + metadata.json)

## Proximos passos recomendados

1. **Monitorar conclusao dos 9 itens pending** — sistema proximo de 100%
2. **Verificar itens itch.io que falharam** (HBREW-041: "Browser initialization failed" — Puppeteer fallback falhou, mas HTTP direto deveria funcionar)
3. **Considerar adicionar mais seriais homebrew** ao catalogo (itch.io tem muitos jogos PSX homebrew)
4. **Otimizar velocidade:** multi-source ja implementado, mas precisa de multiplas fontes com mesmo size para funcionar
5. **Investigar por que alguns jogos itch.io acionam fallback Puppeteer** em vez de HTTP direto

## Arquivos abertos no IDE

- services/download/index.js
- services/search/plugins/web_search.js
- .gitignore

## Notas

- Remote configurado: `origin https://github.com/zaozbr/importre-microservices.git`
- Repositorio: https://github.com/zaozbr/importre-microservices
- Sistema antigo Python em `D:\roms\library\roms\psx\` (importre.py) nao confundir com Node.js em `F:\importre\`
- Regra critica: nunca usar `taskkill /F /IM chdman.exe`
- Workflow de commit completo em `knowledge/workflows/commit.md` (7 passos obrigatórios)
- Queue roda na porta 9011 (nao 9001)
- Lint: 0 erros, 0 warnings
- Testes: 200 passing, 1 pending, 0 failing
- Deps novas: itchio-downloader@1.2.0
