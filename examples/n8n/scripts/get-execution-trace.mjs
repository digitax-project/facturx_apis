#!/usr/bin/env node
// Reads a copy of n8n's own execution database (SQLite) and prints a
// human-readable per-node trace for one execution -- workflow, node
// timeline, and (if present) the assembled ActivityExecution outcome.
//
// n8n already saves this data by default (EXECUTIONS_DATA_SAVE_ON_SUCCESS
// defaults to "all" on the free/community edition -- this is not an
// Enterprise feature). It just stores it in its own internal `flatted`
// serialization, not queryable JSON, and nothing in this project reads it
// back today. This script is that missing read-back step for local/dev use.
// It does NOT replace a real Evidence Store: this is read-only, ad hoc,
// and requires direct access to the n8n container's SQLite file.
//
// Usage:
//   node get-execution-trace.mjs --db <path-to-sqlite-copy> [--correlation-id <id>] [--execution-id <id>] [--list]
//
// The db path must be a COPY of the running instance's database.sqlite
// (`docker cp <container>:/home/node/.n8n/database.sqlite <dest>`), not the
// live file, to avoid contending with n8n's own WAL writes.

import { DatabaseSync } from "node:sqlite";
import { parse } from "flatted";

function parseArgs(argv) {
  const out = { db: null, correlationId: null, executionId: null, list: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--db") out.db = argv[++i];
    else if (argv[i] === "--correlation-id") out.correlationId = argv[++i];
    else if (argv[i] === "--execution-id") out.executionId = argv[++i];
    else if (argv[i] === "--list") out.list = true;
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.db) {
    console.error("Usage: node get-execution-trace.mjs --db <sqlite-copy-path> [--correlation-id <id> | --execution-id <id> | --list]");
    process.exit(1);
  }

  const db = new DatabaseSync(args.db, { readOnly: true });

  if (args.list) {
    const rows = db.prepare(
      "SELECT id, workflowId, status, startedAt, stoppedAt, mode FROM execution_entity ORDER BY id DESC LIMIT 50"
    ).all();
    for (const r of rows) {
      console.log(`#${r.id}  ${r.status.padEnd(9)}  ${r.workflowId}  started=${r.startedAt}  stopped=${r.stoppedAt ?? "(still running / never completed)"}`);
    }
    return;
  }

  let candidateIds;
  if (args.executionId) {
    candidateIds = [Number(args.executionId)];
  } else {
    // No indexed correlationId column exists in n8n's schema -- this is a
    // linear scan over stored execution data, fine for local/dev volumes,
    // not a substitute for a real indexed Evidence Store at scale.
    const all = db.prepare("SELECT executionId FROM execution_data").all();
    candidateIds = all.map((r) => r.executionId);
  }

  let found = false;
  for (const id of candidateIds) {
    const row = db.prepare("SELECT data FROM execution_data WHERE executionId = ?").get(id);
    if (!row) continue;
    if (args.correlationId && !row.data.includes(`"correlationId":"${args.correlationId}"`) && !row.data.includes(args.correlationId)) {
      // cheap pre-filter before the more expensive flatted.parse below
      continue;
    }

    const meta = db.prepare(
      "SELECT id, workflowId, status, startedAt, stoppedAt, mode FROM execution_entity WHERE id = ?"
    ).get(id);

    const data = parse(row.data);
    const runData = data.resultData.runData;

    if (args.correlationId) {
      const hasIt = JSON.stringify(runData).includes(args.correlationId);
      if (!hasIt) continue;
    }

    found = true;
    console.log(`\n=== Execution #${meta.id} -- ${meta.workflowId} -- ${meta.status} ===`);
    console.log(`started:  ${meta.startedAt}`);
    console.log(`stopped:  ${meta.stoppedAt ?? "(still running / never completed)"}`);
    console.log(`mode:     ${meta.mode}`);
    console.log(`\nNode timeline:`);
    for (const [nodeName, runs] of Object.entries(runData)) {
      for (const run of runs) {
        console.log(`  ${String(run.startTime).padEnd(14)}  +${String(run.executionTime).padStart(5)}ms  ${run.executionStatus.padEnd(9)}  ${nodeName}`);
      }
    }

    // Best-effort: find the final ActivityExecution-bearing node output.
    const assembleNode = runData["Merge ActivityExecution into outcome"];
    if (assembleNode) {
      const json = assembleNode[0]?.data?.main?.[0]?.[0]?.json;
      if (json?.activityExecution) {
        console.log(`\nActivityExecution:`);
        console.log(JSON.stringify(json.activityExecution, null, 2));
      }
    }
  }

  if (!found) {
    console.log(args.correlationId ? `No execution found containing correlationId "${args.correlationId}".` : "No executions found.");
  }
}

main();
