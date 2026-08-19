#!/usr/bin/env python3
"""Minimal local dev helper: renders a PDF page to a PNG image.

Not part of the DigiTax product. Exists only because Flow 1b's local AI
lane needs an actual image to hand a local vision model (LM Studio,
Ollama, etc.) -- unlike Gemini's API, most local OpenAI-compatible
endpoints reject a raw PDF passed as an image_url and require a real
rendered image. This is that missing render step, callable over HTTP from
the n8n container the same way LOCAL_LLM_BASE_URL already is
(host.docker.internal).

No PDF content, invoice data, or credentials are logged or persisted --
purely a stateless render-and-respond helper for local development.

Usage:
    python pdf_render_service.py [--port 8098]

Requires: pymupdf (`pip install pymupdf`), stdlib only otherwise.
"""

import argparse
import base64
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import fitz  # pymupdf


class RenderHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Deliberately quiet -- no invoice content in logs.
        pass

    def do_POST(self):
        if self.path != "/render":
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            pdf_bytes = base64.b64decode(body["pdfBase64"])
            page_index = int(body.get("page", 0))
            dpi = int(body.get("dpi", 150))

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if page_index >= len(doc):
                raise ValueError(f"page {page_index} out of range (document has {len(doc)} pages)")
            page = doc[page_index]
            pix = page.get_pixmap(dpi=dpi)
            png_bytes = pix.tobytes("png")
            page_count = len(doc)
            doc.close()

            response = {
                "pngBase64": base64.b64encode(png_bytes).decode("ascii"),
                "width": pix.width,
                "height": pix.height,
                "pageCount": page_count,
            }
            payload = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            payload = json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            payload = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8098)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), RenderHandler)
    print(f"pdf_render_service listening on :{args.port} (POST /render, GET /health)")
    server.serve_forever()
