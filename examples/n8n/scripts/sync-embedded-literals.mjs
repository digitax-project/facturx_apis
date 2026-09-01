#!/usr/bin/env node
// Deterministic sync/check for the generated-literal blocks embedded inside
// n8n Code node jsCode strings (n8n Code nodes cannot `require()` or `import`
// arbitrary repository files at runtime -- the literals must be copied in,
// but never hand-edited once copied).
//
// Two independent embeds are synced:
//
// 1. BINDING/WORKFLOW_BINDINGS inside
//    digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json's
//    "01.1 Assert activity binding published" node, regenerated from
//    examples/n8n/activity_binding.invoice_intake.json (the lockfile
//    examples/n8n/scripts/Sync-ActivityBinding.ps1 already maintains).
//    A1 correction round 1 (High-4): this closes the gap where the lockfile
//    could say v1.1.0 while this embedded copy still said v1.0.0.
//
// 2. The canonical-json-v1 functions inside
//    digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json's
//    "04.3 Evaluate risk review gate" node, regenerated verbatim from the
//    CANONICAL-JSON-V1-BEGIN/END block in examples/n8n/vendor/canonicalJson.js.
//
// Usage:
//   node examples/n8n/scripts/sync-embedded-literals.mjs            # regenerate in place
//   node examples/n8n/scripts/sync-embedded-literals.mjs --check    # throw on drift, write nothing

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const n8nDir = path.dirname(__dirname);
const checkOnly = process.argv.includes("--check");

const LOCKFILE_PATH = path.join(n8nDir, "activity_binding.invoice_intake.json");
const SHARED_ASSEMBLER_PATH = path.join(
  n8nDir,
  "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json"
);
const BATCH_ITEM_PATH = path.join(n8nDir, "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json");
const CANONICAL_JSON_VENDOR_PATH = path.join(n8nDir, "vendor", "canonicalJson.js");

const BINDING_ASSERT_NODE_NAME = "01.1 Assert activity binding published";
const RISK_REVIEW_GATE_NODE_NAME = "04.3 Evaluate risk review gate";

// Normalizes CRLF to LF so the check is content-based rather than
// dependent on the checkout's line-ending conversion (core.autocrlf=true
// on Windows rewrites every text file to CRLF on checkout, which would
// otherwise show up as spurious "drift" against an LF-only regeneration).
function readText(p) {
  return readFileSync(p, "utf8").replace(/\r\n/g, "\n");
}

function loadJson(p) {
  return JSON.parse(readText(p));
}

function writeJson(p, obj) {
  writeFileSync(p, `${JSON.stringify(obj, null, 2)}\n`);
}

function findNode(workflow, name) {
  const node = workflow.nodes.find((n) => n.name === name);
  if (!node) throw new Error(`Node not found: ${name}`);
  return node;
}

function replaceBetweenMarkers(source, beginMarker, endMarker, replacement) {
  const beginIdx = source.indexOf(beginMarker);
  const endIdx = source.indexOf(endMarker);
  if (beginIdx === -1 || endIdx === -1 || endIdx < beginIdx) {
    throw new Error(`Could not locate markers "${beginMarker}" / "${endMarker}"`);
  }
  const beginLineEnd = source.indexOf("\n", beginIdx) + 1;
  return source.slice(0, beginLineEnd) + replacement + source.slice(endIdx);
}

function extractBetweenMarkers(source, beginMarker, endMarker) {
  const beginIdx = source.indexOf(beginMarker);
  const endIdx = source.indexOf(endMarker);
  if (beginIdx === -1 || endIdx === -1 || endIdx < beginIdx) {
    throw new Error(`Could not locate markers "${beginMarker}" / "${endMarker}"`);
  }
  const beginLineEnd = source.indexOf("\n", beginIdx) + 1;
  return source.slice(beginLineEnd, endIdx);
}

// --- 1. BINDING/WORKFLOW_BINDINGS -> shared assembler ---------------------

function regenerateBindingEmbed() {
  const lockfile = loadJson(LOCKFILE_PATH);
  const bindingLiteral = {
    processId: lockfile.processDefinition.processId,
    processVersion: lockfile.processDefinition.processVersion,
    activityId: lockfile.activityDefinition.activityId,
    activityVersion: lockfile.activityDefinition.activityVersion,
    executorType: lockfile.executor.type,
    executorLogicalId: lockfile.executor.logicalId,
    executorVersion: lockfile.executor.version,
  };
  const workflowBindingsLiteral = {};
  for (const b of lockfile.workflowBindings) {
    workflowBindingsLiteral[b.workflowId] = {
      workflowVersion: b.workflowVersion,
      nodeId: b.nodeId,
    };
  }

  const replacement =
    `const BINDING = ${JSON.stringify(bindingLiteral, null, 2)};\n\n` +
    `const WORKFLOW_BINDINGS = ${JSON.stringify(workflowBindingsLiteral, null, 2)};\n`;

  const workflow = loadJson(SHARED_ASSEMBLER_PATH);
  const node = findNode(workflow, BINDING_ASSERT_NODE_NAME);
  node.parameters.jsCode = replaceBetweenMarkers(
    node.parameters.jsCode,
    "// GENERATED-BINDING-BEGIN",
    "// GENERATED-BINDING-END",
    replacement
  );
  return { workflow, path: SHARED_ASSEMBLER_PATH };
}

// --- 2. canonical-json-v1 -> batch item risk review gate -------------------

function regenerateCanonicalJsonEmbed() {
  const vendorSource = readText(CANONICAL_JSON_VENDOR_PATH);
  const functionsSource = extractBetweenMarkers(
    vendorSource,
    "// CANONICAL-JSON-V1-BEGIN",
    "// CANONICAL-JSON-V1-END"
  );

  const workflow = loadJson(BATCH_ITEM_PATH);
  const node = findNode(workflow, RISK_REVIEW_GATE_NODE_NAME);
  node.parameters.jsCode = replaceBetweenMarkers(
    node.parameters.jsCode,
    "// GENERATED-CANONICAL-JSON-BEGIN",
    "// GENERATED-CANONICAL-JSON-END",
    functionsSource
  );
  return { workflow, path: BATCH_ITEM_PATH };
}

const results = [regenerateBindingEmbed(), regenerateCanonicalJsonEmbed()];

if (checkOnly) {
  let drift = false;
  for (const { workflow, path: p } of results) {
    const committed = readText(p);
    const regenerated = `${JSON.stringify(workflow, null, 2)}\n`;
    if (committed !== regenerated) {
      drift = true;
      console.error(`DRIFT: ${p} does not match a fresh regeneration of its embedded literals.`);
    }
  }
  if (drift) {
    throw new Error("Embedded-literal drift detected. Run without --check to regenerate.");
  }
  console.log("OK: embedded literals in both workflows match a fresh regeneration.");
} else {
  for (const { workflow, path: p } of results) {
    writeJson(p, workflow);
    console.log(`Regenerated embedded literals in ${p}`);
  }
}
