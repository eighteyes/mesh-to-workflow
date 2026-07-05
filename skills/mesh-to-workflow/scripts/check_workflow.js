#!/usr/bin/env node
// check_workflow.js
// Syntax-check a compiled Workflow script the way the runtime parses it.
// Responsibilities:
//   - Strip the `export` from the meta block (runtime reads it statically)
//   - Compile the body as an AsyncFunction with the workflow globals in scope,
//     so top-level `return` and `await` are legal (node --check rejects them)
//   - Assert meta has literal name + description
//   - Exit 0 with "syntax OK" or exit 1 with the parse error

const fs = require('fs')

const file = process.argv[2]
if (!file) {
  console.error('usage: check_workflow.js <workflow.js>')
  process.exit(1)
}

const src = fs.readFileSync(file, 'utf8').replace(/^export\s+const\s+meta/m, 'const meta')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

try {
  new AsyncFunction('agent', 'parallel', 'pipeline', 'phase', 'log', 'workflow', 'args', 'budget', src)
} catch (err) {
  console.error(`FAIL: ${err.message}`)
  process.exit(1)
}

const metaMatch = src.match(/const\s+meta\s*=\s*\{[\s\S]*?\n\}/)
if (!metaMatch) {
  console.error('FAIL: no `export const meta = {...}` block found')
  process.exit(1)
}
for (const field of ['name', 'description']) {
  if (!new RegExp(`\\b${field}\\s*:`).test(metaMatch[0])) {
    console.error(`FAIL: meta is missing required field "${field}"`)
    process.exit(1)
  }
}

console.log('syntax OK')
