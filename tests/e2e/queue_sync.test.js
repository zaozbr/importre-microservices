/**
 * queue_sync.test.js — Teste do bug syncCompletedStatus.
 *
 * Bug: itens em q.completed com status != "completed" bloqueiam next-pending.
 * O filtro de next-pending verifica !q.completed[i.serial] e rejeita itens
 * que estao em q.completed mas com status "pending" (inconsistencia).
 *
 * Correcao: syncCompletedStatus() em getQueue() corrige o status automaticamente.
 */
require('../download/_setup');
const { expect } = require('chai');
const fs = require('fs');
const path = require('path');

const QUEUE_SRC = fs.readFileSync(
  path.join(__dirname, '..', '..', 'services', 'queue', 'index.js'), 'utf-8'
);

describe('Queue syncCompletedStatus — Bug -> Teste', function () {
  this.timeout(10000);

  it('syncCompletedStatus deve existir como funcao', () => {
    expect(QUEUE_SRC).to.contain('function syncCompletedStatus');
  });

  it('getQueue deve chamar syncCompletedStatus', () => {
    expect(QUEUE_SRC).to.contain('syncCompletedStatus(queueCache)');
  });

  it('syncCompletedStatus deve corrigir status para completed', () => {
    // Verifica que a funcao seta item.status = 'completed'
    expect(QUEUE_SRC).to.contain("item.status = 'completed'");
  });

  it('syncCompletedStatus deve remover de in_progress', () => {
    expect(QUEUE_SRC).to.contain('delete q.in_progress[item.serial]');
  });

  it('next-pending deve filtrar por !q.completed', () => {
    // O filtro do next-pending verifica q.completed
    expect(QUEUE_SRC).to.contain('!q.completed[i.serial]');
  });

  it('syncCompletedStatus deve ser chamada no reload externo', () => {
    // Verifica que syncCompletedStatus e chamada apos reload externo
    const reloadMatch = QUEUE_SRC.match(/Queue\.json modificado externamente[\s\S]*?syncCompletedStatus/);
    expect(reloadMatch, 'syncCompletedStatus nao chamada apos reload externo').to.not.be.null;
  });
});
