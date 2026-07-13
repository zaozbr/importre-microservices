// ESLint flat config com regras SonarQube (eslint-plugin-sonarjs)
// Foco: CONFIABILIDADE. Regras que pegam bugs reais, nao apenas estilo.
// Qualquer violacao aqui pode causar crash, race condition, ou comportamento
// indefinido em producao. Respeitar todas antes de commitar.
import js from '@eslint/js';
import sonarjs from 'eslint-plugin-sonarjs';
import globals from 'globals';

export default [
  // Base: recomendacoes ESLint (ja inclui muitas regras de bug)
  js.configs.recommended,

  // Plugin SonarJS + regras ESLint extras de confiabilidade
  {
    plugins: { sonarjs },
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      globals: {
        ...globals.node,
        ...globals.es2024,
      },
    },
    rules: {
      // ============================================================
      // SONARJS - todas as regras de bug/correcao como ERROR
      // ============================================================
      'sonarjs/no-all-duplicated-branches': 'error',
      'sonarjs/no-collapsible-if': 'warn',
      'sonarjs/no-collection-size-mischeck': 'error',
      'sonarjs/no-duplicated-branches': 'error',
      'sonarjs/no-element-overwrite': 'error',
      'sonarjs/no-empty-collection': 'error',
      'sonarjs/no-extra-arguments': 'error',
      'sonarjs/no-gratuitous-expressions': 'error',
      'sonarjs/no-identical-conditions': 'error',
      'sonarjs/no-identical-expressions': 'error',
      'sonarjs/no-identical-functions': 'warn',
      'sonarjs/no-ignored-return': 'error',
      'sonarjs/no-inverted-boolean-check': 'error',
      'sonarjs/no-one-iteration-loop': 'error',
      'sonarjs/no-redundant-boolean': 'error',
      'sonarjs/no-redundant-jump': 'error',
      'sonarjs/no-same-line-conditional': 'error',
      'sonarjs/no-unused-collection': 'warn',
      'sonarjs/no-use-of-empty-return-value': 'error',
      'sonarjs/no-useless-catch': 'error',
      'sonarjs/non-existent-operator': 'error',
      'sonarjs/prefer-while': 'warn',

      // Estilo/complexidade - warn para nao travar, mas sinalizar
      'sonarjs/cognitive-complexity': ['warn', 25],
      'sonarjs/max-switch-cases': ['warn', 20],
      'sonarjs/no-duplicate-string': ['warn', { threshold: 5 }],
      'sonarjs/no-nested-switch': 'off',
      'sonarjs/no-nested-template-literals': 'off',
      'sonarjs/no-small-switch': 'off',
      'sonarjs/elseif-without-else': 'off',
      'sonarjs/prefer-immediate-return': 'off',
      'sonarjs/prefer-object-literal': 'off',
      'sonarjs/prefer-single-boolean-return': 'off',

      // ============================================================
      // ESLINT CORE - regras de bug que aumentam confiabilidade
      // ============================================================
      // Erros silenciosos / bugs logicos
      'no-async-promise-executor': 'error',
      'no-class-assign': 'error',
      'no-compare-neg-zero': 'error',
      'no-cond-assign': 'error',
      'no-constant-condition': ['error', { checkLoops: false }],
      'no-debugger': 'error',
      'no-dupe-class-members': 'error',
      'no-dupe-keys': 'error',
      'no-duplicate-case': 'error',
      'no-empty': ['error', { allowEmptyCatch: true }],
      'no-empty-pattern': 'error',
      'no-ex-assign': 'error',
      'no-extra-boolean-cast': 'error',
      'no-fallthrough': 'error',
      'no-func-assign': 'error',
      'no-global-assign': 'error',
      'no-irregular-whitespace': 'error',
      'no-mixed-spaces-and-tabs': 'error',
      'no-new-symbol': 'error',
      'no-obj-calls': 'error',
      'no-octal': 'error',
      'no-redeclare': 'error',
      'no-self-assign': 'error',
      'no-self-compare': 'error',
      'no-sparse-arrays': 'error',
      'no-this-before-super': 'error',
      'no-undef': 'error',
      'no-unexpected-multiline': 'error',
      'no-unreachable': 'error',
      'no-unsafe-finally': 'error',
      'no-unsafe-negation': 'error',
      'no-unused-labels': 'error',
      'no-useless-escape': 'warn',
      'no-with': 'error',
      'require-yield': 'error',
      'use-isnan': 'error',
      'valid-typeof': 'error',
      'no-constant-binary-expression': 'error',
      'no-control-regex': 'off', // FPs em regex de scraping
      'no-prototype-builtins': 'warn',
      'no-extend-native': 'error',
      'no-implicit-globals': 'error',
      'no-new': 'error',
      'no-new-func': 'error',
      'no-new-wrappers': 'error',
      'no-octal-escape': 'error',
      'no-return-assign': 'error',
      'no-sequences': 'error',
      'no-useless-call': 'error',
      'no-useless-concat': 'error',
      'no-useless-return': 'warn',
      'no-void': 'error',
      'no-shadow-restricted-names': 'error',
      'no-multi-assign': 'warn',
      'no-implicit-coercion': ['warn', { allow: ['!!'] }],
      'no-floating-decimal': 'off',
      'yoda': ['warn', 'never', { exceptRange: true }],
      'no-throw-literal': 'error',
      'no-return-await': 'warn',
      'no-param-reassign': ['warn', { props: false }],

      // Boas praticas que evitam bugs
      'eqeqeq': ['error', 'smart'],
      'prefer-const': 'error',
      'no-var': 'error',
      'prefer-rest-params': 'warn',
      'prefer-spread': 'warn',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^(e|logErr|e2|err|error)$' }],
      'no-await-in-loop': 'off', // downloads sao sequenciais por worker
      'require-atomic-updates': 'off', // Node single-thread, causa FPs
      'no-console': 'off', // microservicos usam console.log
      'no-inner-declarations': 'off',
    },
  },

  // Ignorar arquivos nao relevantes para analise
  {
    ignores: [
      'node_modules/**',
      'aria2-1.37.0-win-64bit-build1/**',
      '_debug_*.js',
      '_tmp_*.ps1',
      'tools/health_watchdog.js', // script externo standalone
      '**/dashboard.html',
      '**/*.html',
      '**/*.css',
      'config/**',
      'eslint-report.json',
    ],
  },

  // Testes: regras relaxadas (mocha/chai patterns)
  {
    files: ['tests/**/*.test.js', 'tests/test_*.js'],
    languageOptions: {
      globals: {
        ...globals.node,
        ...globals.es2024,
        ...globals.mocha,
      },
    },
    rules: {
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^(e|logErr|e2|err|error|axiosErr|extractErr|archiveErr)$' }],
      'sonarjs/no-duplicate-string': 'off',
      'sonarjs/cognitive-complexity': 'off',
      'sonarjs/no-identical-functions': 'off',
      'sonarjs/no-duplicated-branches': 'off',
      'no-param-reassign': 'off',
      'max-nested-blocks': 'off',
    },
  },
];
