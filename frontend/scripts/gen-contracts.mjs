/**
 * Generates TypeScript types from contracts/asyncapi.yaml.
 *
 * Usage: node frontend/scripts/gen-contracts.mjs
 *        (or: make contracts)
 */

import { compile } from 'json-schema-to-typescript'
import { load as parseYaml } from 'js-yaml'
import { readFileSync, writeFileSync, mkdirSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const SPEC_PATH = resolve(ROOT, 'contracts/asyncapi.yaml')
const OUTPUT_PATH = resolve(ROOT, 'frontend/src/lib/generated/ws-contract.ts')

const spec = parseYaml(readFileSync(SPEC_PATH, 'utf8'))
const schemas = spec.components.schemas

// Rewrite AsyncAPI $ref paths to JSON Schema $ref paths
function rewriteRefs(obj) {
  if (obj === null || typeof obj !== 'object') return obj
  if (Array.isArray(obj)) return obj.map(rewriteRefs)
  const out = {}
  for (const [k, v] of Object.entries(obj)) {
    out[k] = k === '$ref' && typeof v === 'string'
      ? v.replace('#/components/schemas/', '#/definitions/')
      : rewriteRefs(v)
  }
  return out
}

const definitions = Object.fromEntries(
  Object.entries(schemas).map(([name, schema]) => [name, rewriteRefs(schema)])
)

// Compile all schemas in one pass to avoid duplicate definitions.
// Use a wrapper object with every schema as a property so json-schema-to-typescript
// emits each type exactly once.
const rootSchema = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  title: '_WsContractRoot',
  type: 'object',
  additionalProperties: false,
  properties: Object.fromEntries(
    Object.keys(definitions).map(name => [name, { $ref: `#/definitions/${name}` }])
  ),
  definitions,
}

const raw = await compile(rootSchema, '_WsContractRoot', {
  bannerComment: '',
  additionalProperties: false,
  unknownAny: true,
  enableConstEnums: false,
  style: { singleQuote: true },
})

// Drop the generated _WsContractRoot wrapper interface — we only want the definitions
const output = raw.replace(/^export interface _WsContractRoot \{[^}]*\}\n?/m, '').trimStart()

const header = [
  '/* eslint-disable */',
  '/* This file is auto-generated from contracts/asyncapi.yaml — do not edit by hand */',
  '',
].join('\n')

mkdirSync(dirname(OUTPUT_PATH), { recursive: true })
writeFileSync(OUTPUT_PATH, header + output)
console.log(`Wrote ${OUTPUT_PATH.replace(ROOT + '/', '')}`)
