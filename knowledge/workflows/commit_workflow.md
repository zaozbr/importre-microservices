# Workflow de Commit

1. Verificar status: `git status --short`
2. Revisar diff: `git diff --stat`
3. Escrever mensagem focada em "por que".
4. Stage: `git add -A`
5. Commit com assinatura Devin.
6. Push apenas se houver remote e sem conflitos.

## Regras

- Nunca `git push --force`.
- Nunca atualizar git config.
- Nao commitar secrets.
- Se pre-commit hooks falharem, revisar e re-tentar.
