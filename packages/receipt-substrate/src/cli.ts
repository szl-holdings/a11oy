#!/usr/bin/env node
import * as path from "node:path";
import {
  appendReceiptJsonl,
  createToolEnvelope,
  emitReceipt,
  readReceiptJsonl,
  verifyChain,
  type ReceiptProtocol,
} from "./index.ts";

interface CliArgs {
  out: string;
  actor: string;
  tool: string;
  protocol: ReceiptProtocol;
  payloadJson: string;
  quorum: string;
  nodes: string[];
  lambdaAxes: string[];
}

function parseArgs(argv: readonly string[]): CliArgs {
  const args = new Map<string, string>();
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const value = argv[i + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }
    args.set(key, value);
    i += 1;
  }

  const out = args.get("out");
  const actor = args.get("actor");
  const tool = args.get("tool");
  const payloadJson = args.get("payload-json");
  if (!out || !actor || !tool || !payloadJson) {
    throw new Error("Required: --out <file> --actor <id> --tool <name> --payload-json <json>");
  }

  return {
    out,
    actor,
    tool,
    payloadJson,
    protocol: (args.get("protocol") ?? "mcp") as ReceiptProtocol,
    quorum: args.get("quorum") ?? "1-of-1",
    nodes: (args.get("nodes") ?? "local-operator").split(",").map((node) => node.trim()).filter(Boolean),
    lambdaAxes: (args.get("lambda-axes") ?? "Λ7").split(",").map((axis) => axis.trim()).filter(Boolean),
  };
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const payload = JSON.parse(args.payloadJson) as unknown;
  const out = path.resolve(args.out);
  const chain = readReceiptJsonl(out);
  const previousReceipt = chain.length > 0 ? chain[chain.length - 1] : null;

  const envelope = createToolEnvelope({
    protocol: args.protocol,
    actor_id: args.actor,
    tool_name: args.tool,
    lambda_axes: args.lambdaAxes,
    payload,
    metadata: {
      source: "a11oy-receipt-substrate-cli",
    },
  });

  const receipt = emitReceipt(envelope, {
    previousReceipt,
    policy: {
      algorithm: "SHA3-256",
      chaining: "hash_chain",
      quorum: args.quorum,
      nodes: args.nodes,
    },
  });

  const nextChain = [...chain, receipt];
  const verification = verifyChain(nextChain, {
    quorum: args.quorum,
    nodes: args.nodes,
  });

  if (!verification.valid) {
    throw new Error(`Refusing to append invalid receipt: ${verification.errors.join("; ")}`);
  }

  appendReceiptJsonl(out, receipt);
  console.log(JSON.stringify({
    ok: true,
    out,
    receipt_id: receipt.receipt_id,
    merkle_root: receipt.merkle_root,
    sequence: receipt.sequence,
  }));
}

try {
  main();
} catch (error) {
  console.error((error as Error).message);
  process.exit(1);
}
