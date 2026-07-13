# Workflow de Commit

1. Verificar status: `git status --short`
2. Revisar diff: `git diff --stat`
3. **Pre-commit checks (OBRIGATORIO, nao pular):**
   a. `npm run lint` — deve passar com 0 erros e 0 warnings
   b. `npm test` — deve passar com 0 falhas
   c. Se qualquer check falhar, CORRIGIR antes de commitar. Nunca commitar codigo que falha em lint ou testes.
4. Escrever mensagem focada em "por que".
5. Stage: `git add -A`
6. Commit com assinatura Devin.
7. Push apenas se houver remote e sem conflitos.

## Regras

- Nunca `git push --force`.
- Nunca atualizar git config.
- Nao commitar secrets.
- Se pre-commit hooks falharem, revisar e re-tentar.
- **Lint e testes sao obrigatorios antes de todo commit.** Sem excecoes.
