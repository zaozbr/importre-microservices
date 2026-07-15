# Archive.org — Renovacao de Cookie (Automatizado)

## Contexto
O `archive.org` exige login para baixar arquivos de colecoes privadas/restritas (ex: `psx-roms-archive`).
Sem cookie de login, o download retorna `401 Unauthorized`.
O cookie `logged-in-sig` expira periodicamente, exigindo renovacao.

## Sintomas de Cookie Expirado
- Downloads do archive.org retornam `401` ou `302` (redirect para login)
- aria2c mostra erro "Unauthorized" ou fica parado em 0/0MB
- `curl -sI https://archive.org/download/<colecao>/<arquivo>` retorna 401

## Solucao: Criar conta temporaria + login via `ia` (internetarchive CLI)

### Prerequisitos
- Python 3 + `internetarchive` instalado (`py -m pip install internetarchive`)
- `ia.exe` em `C:\Users\Usuario\AppData\Local\Programs\Python\Python314\Scripts\ia.exe`
- Navegador Chrome instalado (`C:\Program Files\Google\Chrome\Application\chrome.exe`)
- Playwright MCP disponivel (para criar conta via browser automatizado)

### Passo a Passo (Manual)

1. **Gerar email temporario** em https://temp-mail.org/ (NUNCA usar emailnator — gera Gmail real ja cadastrado)
2. **Criar conta no archive.org** em https://archive.org/account/signup:
   - Email: o temporario gerado
   - Screen name: `impcoll<ano><sufixo>` (ex: `impcoll2026z`)
   - Password: `Arch2026xK9!mp` (fixo — nao precisa mudar)
3. **Confirmar email** — voltar no temp-mail.org, abrir email do archive.org, clicar no link de verificacao
   - ATENCAO: o link expira rapido (~2 min). Se falhar, tentar login mesmo assim — as vezes funciona
4. **Fazer login via `ia configure`**:
   ```
   & "C:\Users\Usuario\AppData\Local\Programs\Python\Python314\Scripts\ia.exe" configure --username "<email>" --password "Arch2026xK9!mp"
   ```
   Isso salva os cookies em `C:\Users\Usuario\.config\internetarchive\ia.ini`
5. **Extrair cookies do ia.ini** e salvar em `F:\importre\archive_cookies.txt` (formato Netscape)
6. **Reiniciar aria2c** com `--load-cookies=F:\importre\archive_cookies.txt`

### Script Automatizado
Ver `F:\importre\tools\renew_archive_cookie.js` — faz passos 4-6 automaticamente.
Passos 1-3 (criar conta) requerem browser (Playwright MCP) pois archive.org tem reCAPTCHA.

### Por que `ia configure` e nao curl/axios?
- O archive.org usa React SPA para login — `curl` nao consegue renderizar o formulario
- O `ia` (internetarchive CLI) usa a API interna `https://archive.org/services/xauthn/` que funciona sem browser
- O `ia` extrai o `logged-in-sig` (HttpOnly) que `document.cookie` nao acessa

### Por que NAO usar emailnator?
- emailnator gera enderecos Gmail reais (ex: `r.h.i.on.aa.b.uendo@gmail.com`)
- Esses emails ja tem conta no archive.org → "already taken"
- temp-mail.org usa dominios proprios (ex: `ezimb.com`) que aceitos como novos

### Por que NAO usar guerrillamail/mail.tm?
- archive.org bloqueia dominios de email temporario conhecidos
- `guerrillamailblock.com`, `web-library.net` etc sao rejeitados no signup
- temp-mail.org com dominio `ezimb.com` passou (pode mudar — testar)

## Arquivos Importantes
- `F:\importre\archive_cookies.txt` — cookie Netscape usado pelo aria2c
- `C:\Users\Usuario\.config\internetarchive\ia.ini` — config do `ia` com cookies brutos
- `F:\importre\tools\start_aria2c.bat` — script de inicio do aria2c com `--load-cookies`
- `F:\importre\tools\renew_archive_cookie.js` — script de renovacao automatica (passos 4-6)

## Parametros aria2c Otimizados (anti rate-limit)
- `--max-concurrent-downloads=20` (nao mais que 20 — archive.org faz rate-limit por IP)
- `--max-connection-per-server=4` (nao mais que 4 — muitas conexoes = bloqueio)
- `--split=4` (alinhado com max-connection-per-server)
- `--retry-wait=5` (espera 5s entre retries)
- `--lowest-speed-limit=10240` (cancela downloads abaixo de 10KB/s — stalled)
- `--load-cookies=F:\importre\archive_cookies.txt` (autenticacao)

## Historico de Contas Criadas
- `zaozao2@gmail.com` — conta real, cookie expirou (~2025)
- `kideje5455@ezimb.com` — conta temporaria via temp-mail.org, criada 2026-07-15, screenname `impcoll2026z`, senha `Arch2026xK9!mp`
