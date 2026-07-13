const { titleScore } = require('../services/search/plugins/_base');

// Testa casos problematicos
const tests = [
  // [target, candidate, esperado >= 0.7?]
  ['SLPM-87014', 'r japan', false],  // serial vs nome curto errado
  ['R (Japan)', 'final fantasy vii', false],  // nomes diferentes
  ['Final Fantasy VII', 'final fantasy vii', true],  // match exato
  ['Dance Dance Revolution 5th Mix', 'dance dance revolution', true],  // subset
  ['Crash Bandicoot', 'crash bandicoot', true],  // exato
  ['Metal Gear Solid', 'metal gear solid', true],  // exato
  ['Resident Evil 2', 'resident evil 2', true],  // exato
  ['Tekken 3', 'tekken 3', true],  // exato
  ['R (Japan)', 'r japan', true],  // auto-match
];

console.log('=== Teste titleScore ===\n');
let pass = 0, fail = 0;
for (const [target, candidate, expected] of tests) {
  const score = titleScore(target, candidate);
  const result = score >= 0.7;
  const ok = result === expected;
  console.log(`${ok ? 'PASS' : 'FAIL'}: "${target}" vs "${candidate}" = ${score.toFixed(2)} (esperado ${expected ? '>=0.7' : '<0.7'})`);
  if (ok) pass++; else fail++;
}
console.log(`\n${pass}/${tests.length} passaram, ${fail} falharam`);
