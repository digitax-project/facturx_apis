#!/usr/bin/env python3
"""Deterministic local-AI + PDF-render test double for Flow 1b E2E testing
(tests/test_n8n_flow1b_workflow.py). Not part of the product; stdlib only.

By default, /chat/completions always returns the same canned, valid-looking
invoice extraction regardless of input, so the workflow's real HTTP-call/
parse/normalize wiring is exercised end-to-end without depending on a real
local vision model. Set FLOW1B_STUB_MALFORMED=1 to make /chat/completions
return a response whose message.content is not valid JSON, exercising
"02.5L Parse local OCR/LLM output"'s malformed-model-output failure path.
"""
import base64
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MALFORMED = os.environ.get("FLOW1B_STUB_MALFORMED", "") == "1"

CANNED_INVOICE = {
    "Invoice No": "UX-LOCAL-001",
    "Invoice Date": "2026-08-20",
    "Type Code": "380",
    "Currency": "EUR",
    "VAT-ID (Seller)": "DE111111111",
    "VAT-ID (Buyer)": "not found",
    "Tax ID (Seller)": "not found",
    "Tax ID (Buyer)": "not found",
    "Name (Seller)": "Beispiel Lieferant GmbH",
    "Address (Seller)": "Lieferweg 1",
    "Zip (Seller)": "10115",
    "City (Seller)": "Berlin",
    "Country (Seller)": "DE",
    "Name (Buyer)": "Unternehmen X",
    "Address (Buyer)": "Musterweg 10",
    "Zip (Buyer)": "04109",
    "City (Buyer)": "Leipzig",
    "Country (Buyer)": "DE",
    "Supply Description": "Synthetic consulting service",
    "Delivery Date": "2026-08-18",
    "Period Start": "not found",
    "Period End": "not found",
    "Net Total": 100.0,
    "Tax Basis": 100.0,
    "Tax Amount": 19.0,
    "Gross Total": 119.0,
    "Payable Amount": 119.0,
    "Charge Total": 0.0,
    "Allowance Total": 0.0,
    "Prepaid Amount": 0.0,
    "Rounding Amount": 0.0,
    "Line Items": [
        {"Description": "Synthetic consulting service", "Quantity": 1.0, "Net Amount": 100.0, "VAT Rate": 19.0}
    ],
}

# A minimal valid 1x1 PNG.
TINY_PNG_BASE64 = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001080600000"
        "01f15c4890000000a49444154789c6360000002000155007a0e0e1a00"
        "0000004945454e44ae426082"
    )
).decode("ascii")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, status=200):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.path == "/render":
            self._send_json({"pngBase64": TINY_PNG_BASE64, "width": 1, "height": 1, "pageCount": 1})
        elif self.path == "/chat/completions":
            content = "this is not valid JSON at all {{{" if MALFORMED else json.dumps(CANNED_INVOICE)
            self._send_json({"choices": [{"message": {"content": content}}]})
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8098), Handler)
    print("flow1b_local_ai_stub listening on :8098 (POST /render, POST /chat/completions, GET /health)")
    server.serve_forever()
