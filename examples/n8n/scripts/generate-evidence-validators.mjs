#!/usr/bin/env node
// Build-time-only AJV-standalone validator generator. Reads only the
// vendored, hash-pinned P2.1 schema snapshots under examples/n8n/vendor/p2_1/
// -- never the research workspace directly, so a normal CI checkout of only
// this repository has everything it needs.
//
// Scope (P2.1 Wave 1 A5 Stage 0/1): ActivityExecution is the only validator
// generated and embedded. HumanReviewDecision is vendored (Stage 0 keeps the
// P2.1 schema pair atomically hash-pinned together) but deliberately NOT
// compiled here -- that belongs to Flow 2, which is out of this
// implementation's authorized scope. validator_provenance.json records this
// explicitly so the deferral is never silently lost.
//
// Regenerate via: node examples/n8n/scripts/generate-evidence-validators.mjs

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import path from "node:path";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import ajvFormatsFormats from "ajv-formats/dist/formats.js";
import standaloneCode from "ajv/dist/standalone/index.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const n8nDir = path.dirname(__dirname);
const vendorDir = path.join(n8nDir, "vendor", "p2_1");
const tcmsContractsDir = path.join(n8nDir, "vendor", "tcms_contracts");
const schemasDir = path.join(n8nDir, "schemas");
const generatedDir = path.join(n8nDir, "generated");
const require = createRequire(import.meta.url);

const GENERATOR_VERSION = "1.0.0";
const GENERATED_HEADER =
  "// GENERATED FILE -- do not hand-edit. Regenerate via node examples/n8n/scripts/generate-evidence-validators.mjs\n";

function sha256Hex(filePath) {
  return createHash("sha256").update(readFileSync(filePath)).digest("hex");
}

// AJV's standalone codegen references a couple of small, pure runtime
// helpers (e.g. ajv/dist/runtime/ucs2length, used by minLength/maxLength)
// via `require("<module>").default` rather than inlining their source.
// That require would fail inside a sandboxed n8n Code node (no ajv package
// present, NODE_FUNCTION_ALLOW_EXTERNAL left at its default/unset), so it
// must be resolved at generation time, not left in the committed output.
// Each helper here is a small, self-contained function with no closure over
// external state (verified by reading ajv's own source), so
// Function.prototype.toString() reproduces fully standalone, runtime-safe
// source -- this is generation-time-only bundling, not a new runtime
// dependency.
function inlineRuntimeRequire(code, modulePath, exportProp) {
  const requireExpr = exportProp
    ? `require("${modulePath}").${exportProp}`
    : `require("${modulePath}")`;
  if (!code.includes(requireExpr)) {
    return code;
  }
  const fn = exportProp ? require(modulePath)[exportProp] : require(modulePath);
  if (typeof fn !== "function") {
    throw new Error(`Expected a function at require("${modulePath}")${exportProp ? `.${exportProp}` : ""}`);
  }
  const inlineSource = `(${fn.toString()})`;
  return code.split(requireExpr).join(inlineSource);
}

// Compiles one schema into a standalone, dependency-free JS function
// expression named `exportedFunctionName`, with no module.exports wrapper
// (Code-node sandboxes have no CommonJS `module` global) and no `require`
// at all in the final output.
function compileStandaloneFunction(schema, exportedFunctionName) {
  const ajv = new Ajv2020({
    code: { source: true, esm: false },
    allErrors: true,
  });
  // Registers the full standard format set (future-proofing for any other
  // schema this generator might compile), but ajv-formats' own "date-time"
  // entry in "full" mode is a calendar-aware *function*, which AJV's
  // standalone codegen can only reference via a runtime require of the
  // ajv-formats package -- unacceptable inside an n8n Code node sandbox.
  // ajv-formats' "fast" mode date-time entry is a plain RegExp, which AJV
  // *can* serialize as a literal with no require. Re-registering exactly
  // "date-time" (the only format either P2.1 schema actually uses) with
  // that regex -- sourced from ajv-formats itself, not hand-written -- keeps
  // format:"date-time" genuinely enforced (proven by test 12) while keeping
  // the generated output self-contained.
  addFormats(ajv, { mode: "fast" });
  ajv.addFormat("date-time", ajvFormatsFormats.fastFormats["date-time"].validate);

  const validate = ajv.compile(schema);
  let moduleCode = standaloneCode(ajv, validate);

  moduleCode = inlineRuntimeRequire(moduleCode, "ajv/dist/runtime/ucs2length", "default");
  moduleCode = inlineRuntimeRequire(moduleCode, "ajv/dist/runtime/equal", "default");
  moduleCode = inlineRuntimeRequire(moduleCode, "ajv/dist/runtime/uri", "default");

  if (moduleCode.includes("require(")) {
    const remaining = [...moduleCode.matchAll(/require\("[^"]+"\)/g)].map((m) => m[0]);
    throw new Error(
      `Generated validator still contains unresolved require() calls: ${[...new Set(remaining)].join(", ")}`
    );
  }

  const exportMatch = moduleCode.match(/module\.exports\s*=\s*(\w+);/);
  if (!exportMatch) {
    throw new Error("Could not locate AJV standalone module.exports function name.");
  }
  const internalName = exportMatch[1];

  const withoutExports = moduleCode
    .replace(/module\.exports\s*=\s*\w+;/, "")
    .replace(/module\.exports\.default\s*=\s*\w+;/, "");

  const renamed = withoutExports.replace(
    new RegExp(`\\b${internalName}\\b`, "g"),
    exportedFunctionName
  );

  return renamed;
}

function generateActivityExecutionValidator() {
  const schemaFileName = "activity-execution.schema.json";
  const schemaPath = path.join(vendorDir, schemaFileName);
  const schema = JSON.parse(readFileSync(schemaPath, "utf8"));

  const functionSource = compileStandaloneFunction(schema, "validateActivityExecution");
  const fileContent = `${GENERATED_HEADER}${functionSource}\n`;

  mkdirSync(generatedDir, { recursive: true });
  const outPath = path.join(generatedDir, "validate_activity_execution.generated.js");
  writeFileSync(outPath, fileContent);

  return {
    outPath,
    sourceSha256: sha256Hex(schemaPath),
  };
}

function generateRiskReviewReportValidator() {
  // A6a correction round 1 (plan section 5): the accepted A5b RiskReviewReport
  // 1.1 schema, vendored verbatim in examples/n8n/vendor/tcms_contracts/ with
  // its own source hash/provenance (see schema_provenance.json there).
  // Embedded into the Batch Item workflow's "04.6 Handle risk review
  // response" node so a 2xx response is only ever accepted when it fully
  // validates -- never merely presence-checked.
  const schemaFileName = "risk-review-report-v1.2.0.schema.json";
  const schemaPath = path.join(tcmsContractsDir, schemaFileName);
  const schema = JSON.parse(readFileSync(schemaPath, "utf8"));

  const functionSource = compileStandaloneFunction(schema, "validateRiskReviewReport");
  const fileContent = `${GENERATED_HEADER}${functionSource}\n`;

  mkdirSync(generatedDir, { recursive: true });
  const outPath = path.join(generatedDir, "validate_risk_review_report.generated.js");
  writeFileSync(outPath, fileContent);

  return {
    outPath,
    sourceSha256: sha256Hex(schemaPath),
  };
}

function generateResultBundleValidator() {
  // A6a correction round 1 (plan section 6): the frozen TCMS-facing result
  // envelope, authored in this repository (not vendored -- A5c does not yet
  // define its own copy) at examples/n8n/schemas/result-bundle-v1.0.0.schema.json.
  // Embedded into the Batch Item workflow's "04.7 Assemble result bundle"
  // node immediately after bundle assembly.
  const schemaFileName = "result-bundle-v1.0.0.schema.json";
  const schemaPath = path.join(schemasDir, schemaFileName);
  const schema = JSON.parse(readFileSync(schemaPath, "utf8"));

  const functionSource = compileStandaloneFunction(schema, "validateResultBundle");
  const fileContent = `${GENERATED_HEADER}${functionSource}\n`;

  mkdirSync(generatedDir, { recursive: true });
  const outPath = path.join(generatedDir, "validate_result_bundle.generated.js");
  writeFileSync(outPath, fileContent);

  return {
    outPath,
    sourceSha256: sha256Hex(schemaPath),
  };
}

function writeProvenance(activityExecutionResult, riskReviewReportResult, resultBundleResult) {
  const humanReviewDecisionSchemaPath = path.join(vendorDir, "human-review-decision.schema.json");

  const provenance = {
    "activity-execution": {
      sourceSha256: activityExecutionResult.sourceSha256,
      generatorVersion: GENERATOR_VERSION,
      status: "GENERATED",
    },
    "human-review-decision": {
      sourceSha256: sha256Hex(humanReviewDecisionSchemaPath),
      generatorVersion: GENERATOR_VERSION,
      status: "DEFERRED_NOT_GENERATED_FLOW_2_OUT_OF_SCOPE",
    },
    "risk-review-report": {
      sourceSha256: riskReviewReportResult.sourceSha256,
      generatorVersion: GENERATOR_VERSION,
      status: "GENERATED",
    },
    "result-bundle": {
      sourceSha256: resultBundleResult.sourceSha256,
      generatorVersion: GENERATOR_VERSION,
      status: "GENERATED",
    },
  };

  const provenancePath = path.join(generatedDir, "validator_provenance.json");
  writeFileSync(provenancePath, `${JSON.stringify(provenance, null, 2)}\n`);
  return provenancePath;
}

const activityExecutionResult = generateActivityExecutionValidator();
const riskReviewReportResult = generateRiskReviewReportValidator();
const resultBundleResult = generateResultBundleValidator();
const provenancePath = writeProvenance(activityExecutionResult, riskReviewReportResult, resultBundleResult);

console.log(`Generated ${activityExecutionResult.outPath}`);
console.log(`Generated ${riskReviewReportResult.outPath}`);
console.log(`Generated ${resultBundleResult.outPath}`);
console.log(`Generated ${provenancePath}`);
console.log(
  "human-review-decision.schema.json is vendored for atomic P2.1 hash-pinning only; no validator was generated for it (Flow 2 out of scope)."
);
