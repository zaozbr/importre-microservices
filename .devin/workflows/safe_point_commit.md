# Workflow: Safe Point + Commit

## Trigger

O usuario digitar o termo: `documentar tudo do sistema`.

## Acoes obrigatorias

1. **Documentar o sistema**
   - Atualizar `knowledge/system_docs.md` com:
     - Arquitetura atual (servicos, portas, responsabilidades)
     - Principais arquivos e seus papeis
     - Configuracoes (env vars, paths, dependencias)
     - Decisoes recentes e mudancas de design

2. **Documentar licoes aprendidas**
   - Atualizar `knowledge/lessons_learned.md` com novos aprendizados, bugs, correcoes e padroes.

3. **Documentar frustracoes/raiva**
   - Atualizar `knowledge/frustration_log.md` com:
     - Data/hora
     - Contexto do problema
     - Causa raiz
     - Acao corretiva tomada
   - Manter tom objetivo; nao atribuir emocoes ao usuario, apenas registrar eventos que geraram retrabalho ou correcoes urgentes.

4. **Documentar knowledge**
   - Garantir que `knowledge/` esteja sincronizado com:
     - `workflows/commit_workflow.md` (se nao existir, criar)
     - `handover.md` (ultimo estado)
     - `lessons_learned.md`
     - `frustration_log.md`
     - `system_docs.md`

5. **Criar handover**
   - Atualizar `knowledge/handover.md` com:
     - Estado atual do sistema (rodando/parado, portas)
     - Ultimas tarefas em andamento ou completas
     - Proximos passos recomendados
     - Arquivos abertos no IDE
     - PIDs/processos relevantes

6. **Git: aceitar/stage todos os arquivos**
   - `git add -A` (incluir arquivos novos, modificacoes e delecoes)

7. **Criar commit local**
   - Mensagem focada em safe point + timestamp
   - Incluir "Generated with Devin" e Co-Authored-By

8. **Subir commit**
   - `git push` (se houver remote configurado e usuario nao tenha desativado)

9. **Criar safe point em pasta gitignored**
   - Copiar todo o conteudo de `F:\importre\` para `.devin/safe_point/`.
   - `.devin/safe_point/` deve estar no `.gitignore`.

10. **Criar backup dos arquivos alterados em pasta gitignored**
    - Identificar arquivos modificados via `git status --short`.
    - Copiar esses arquivos para `.devin/backups/YYYY-MM-DD_HH-MM-SS/`.
    - `.devin/backups/` deve estar no `.gitignore`.

## Ordem de execucao

1. Reabsorver `AGENTS.md`, `knowledge/lessons_learned.md`, `knowledge/workflows/commit_workflow.md`, `knowledge/handover.md`.
2. Criar/atualizar documentacao em `knowledge/`.
3. Atualizar `.gitignore` se necessario.
4. Criar `safe_point` e `backup`.
5. `git add -A`.
6. `git commit`.
7. `git push`.
8. Reportar resumo ao usuario.

## Notas

- NUNCA usar `git push --force`.
- Se push falhar por conflito, abortar e alertar o usuario.
- Nao incluir secrets, chaves ou credenciais nos commits.
