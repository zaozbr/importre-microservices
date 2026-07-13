# Sincronização de TODOs com TODOs Tree

## Regra

Toda vez que o `todo_write` for usado para criar ou atualizar a lista de tarefas, o arquivo `TODO` na raiz do projeto deve ser sincronizado para refletir o estado atual.

## Formato do arquivo `TODO`

Usar o formato da extensão **Todo+** (vscode-todo-plus):

```
Projeto:
  Subprojeto:
    ☐ Tarefa pendente
    ✔ Tarefa concluida
    ✘ Tarefa cancelada
```

## Procedimento

1. Após usar `todo_write`, ler o arquivo `TODO` atual.
2. Atualizar o status dos itens conforme o `todo_write`.
3. Adicionar novos itens se necessário.
4. Commitar junto com a mudança principal.

## Marcação inline

Para TODOs menores dentro do código, usar comentários no formato reconhecido pela extensão:

```javascript
// TODO: descrição curta
```

```python
# TODO: descrição curta
```

A extensão `vscode-todo-highlight` também destaca esses padrões.
