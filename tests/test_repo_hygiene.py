"""Cross-cutting checks that aren't specific to one feature area.

test_tracked_shell_scripts_have_no_crlf guards a real, previously-shipped
bug: a Windows checkout with the common `core.autocrlf=true` setting
silently converts a committed LF shell script to CRLF unless
`.gitattributes` forces `eol=lf` for it. A CRLF-corrupted `set -eu` line
becomes `set -eu\r`, which `sh` rejects with "illegal option -", which
fails compose.dev.yml's `n8n-init` step and, correctly, the whole
`docker compose up` (n8n never starts) -- reproduced empirically against a
genuinely fresh `git clone` with `core.autocrlf=true` before
`.gitattributes` was added. This test checks the actual bytes on disk, not
the `.gitattributes` policy itself, so it still fails if a future script is
added without the corresponding `.gitattributes` line, or if `.gitattributes`
is ever removed/narrowed.
"""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _tracked_shell_scripts() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.sh"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line]


def test_tracked_shell_scripts_have_no_crlf():
    scripts = _tracked_shell_scripts()
    assert scripts, "expected at least one tracked *.sh file (examples/n8n/scripts/n8n-init.sh)"

    for path in scripts:
        raw = path.read_bytes()
        assert b"\r" not in raw, (
            f"{path.relative_to(REPO_ROOT)} contains a carriage return -- "
            "CRLF line endings will break `sh` execution inside a Linux "
            "container. Check .gitattributes has a `*.sh text eol=lf` rule "
            "covering this path, and that the working tree file itself was "
            "saved with LF endings."
        )


def test_gitattributes_forces_lf_for_shell_scripts():
    attrs = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attrs
