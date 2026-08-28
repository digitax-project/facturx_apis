"use strict";
// Deterministic recursive JSON canonicalization, version "canonical-json-v1".
// Byte-for-byte port of the accepted A5b TCMS implementation
// (server/utils/canonicalJson.ts, tcms-framework worktree
// .claude/worktrees/a2-tcms-baseline-correction): object keys are sorted
// recursively at every nesting level before serialization, so the resulting
// string -- and any hash computed over it -- is independent of the source
// object's key-insertion order. This is what makes a hash computed here
// equal the hash A5b independently recomputes after a JSONB round trip
// (PostgreSQL's jsonb column type does not preserve object key order).
//
// The block between the CANONICAL-JSON-V1-BEGIN/END markers is embedded
// literally into n8n Code nodes by
// examples/n8n/scripts/sync-embedded-literals.mjs -- never read from disk at
// n8n runtime. Do not add anything between the markers that depends on a
// module system (require/module.exports); that lives outside the markers,
// below, for this file's own Node.js test harness use only.

// CANONICAL-JSON-V1-BEGIN
const CANONICAL_JSON_VERSION = "canonical-json-v1";

function canonicalJsonStringifyValue(value) {
  if (value === undefined || value === null) {
    return "null";
  }
  if (typeof value === "boolean" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new TypeError("canonicalJsonStringify: cannot serialize a non-finite number");
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJsonStringifyValue(item)).join(",")}]`;
  }
  if (typeof value === "object") {
    const record = value;
    const keys = Object.keys(record)
      .filter((key) => record[key] !== undefined)
      .sort();
    return `{${keys
      .map((key) => `${JSON.stringify(key)}:${canonicalJsonStringifyValue(record[key])}`)
      .join(",")}}`;
  }
  throw new TypeError(`canonicalJsonStringify: unsupported value type ${typeof value}`);
}

function canonicalJsonStringify(value) {
  return canonicalJsonStringifyValue(value);
}

function canonicalPayloadSha256(payload) {
  const nodeCrypto = require("crypto");
  return nodeCrypto
    .createHash("sha256")
    .update(canonicalJsonStringify(payload), "utf8")
    .digest("hex");
}
// CANONICAL-JSON-V1-END

module.exports = { CANONICAL_JSON_VERSION, canonicalJsonStringify, canonicalPayloadSha256 };
