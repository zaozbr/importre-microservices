---
description: Workflow completo de commit para o projeto Importre — 7 passos obrigatórios
---

# Workflow `commit!` — Importre Microservices (7 Passos Obrigatórios)

**Executado automaticamente quando o usuário digita `commit!` (sem aspas).**

---

## Passo 1: DOCUMENTAR

Atualizar todos os documentos de progresso do projeto:
- `knowledge/lessons_learned.md` — o que foi feito, erros cometidos, lições aprendidas
- `knowledge/frustration_log.md` — frustrações e bloqueios encontrados (as "raivas")
- `knowledge/handover.md` — estado atual, próximas tarefas, arquivos abertos
- `knowledge/` — avanços, TODOs, estado atual do projeto

## Passo 2: BACKUP

Gerar arquivo compactado com timestamp no nome:
```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
Compress-Archive -Path "F:\importre\services","F:\importre\shared","F:\importre\tools","F:\importre\orchestrator","F:\importre\knowledge" `
  -DestinationPath "F:\importre\safe_point\backup_$ts`_descricao.zip"
```
- Incluir arquivos de código-fonte e knowledge
- Guardar em `F:\importre\safe_point/`

## Passo 3: SAFE POINT

Criar diretório com cópia completa dos arquivos fonte críticos:
```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -Path "F:\importre\safe_point\safepoint_$ts" -ItemType Directory -Force
# Copiar: services/, shared/, tools/, orchestrator/, knowledge/, tests/
```

## Passo 4: PRE-COMMIT CHECKS (OBRIGATÓRIO)

a. `npm run lint` — deve passar com 0 erros e 0 warnings
b. `npm test` — deve passar com 0 falhas
c. Se qualquer check falhar, CORRIGIR antes de commitar

## Passo 5: GIT STAGE + COMMIT

Adicionar ao staging apenas arquivos de código-fonte e documentação:
```bash
cd F:\importre
git add services/ shared/ tools/ orchestrator/ knowledge/ tests/ *.js *.json *.md
```
**NUNCA adicionar:** `archive_cookies.txt` (secret), `node_modules/`, `_tmp_*`, `.playwright-mcp/`, `logs/commit_msg.txt`

Commit com assinatura Devin:
```
<tipo>: <descricao curta>

- <mudanca 1>
- <mudanca 2>

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>
```

Tipos: `feat:`, `fix:`, `refactor:`, `docs:`, `build:`, `test:`, `chore:`

## Passo 6: GIT PUSH

Sincronizar com servidor remoto:
```bash
git push
```
Verificar se push foi bem-sucedido. Se não houver remote, pular silenciosamente.

## Passo 7: CONTEXTO

Gerar arquivo de reabsorção em `F:\importre\safe_point\context_<timestamp>.md`:
- Commit mais recente (hash + mensagem)
- Resumo do que foi feito na sessão
- Arquivos-chave modificados
- Regras ativas no momento
- Próximos passos pendentes

---

## Regras Adicionais

- `archive_cookies.txt` contém credenciais — NUNCA commitar
- `node_modules/` é ignorado via `.gitignore`
- Scripts em `logs/` são temporários — avaliar caso a caso
- Sempre verificar lint + test antes de commitar
- Este workflow é uma **regra inegociável** e deve ser reabsorvida antes de cada sessão
- O workflow anterior `commit_workflow.md` foi substituído por este (mais completo)
