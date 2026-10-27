"""Optional Windows launcher for Edge versions that reject Playwright's pipe mode."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=shutil.which("node"))
    parser.add_argument("--playwright-module")
    parser.add_argument("--edge", default=str(Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe"))
    args = parser.parse_args()
    if not args.node or not Path(args.edge).is_file():
        parser.error("Node.js and installed Microsoft Edge are required")
    project = Path(__file__).resolve().parents[1]
    temporary = project.parents[1] / "tmp"
    temporary.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="edge-e2e-", dir=temporary) as profile:
        process = subprocess.Popen(
            [args.edge, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox",
             f"--user-data-dir={profile}", "--remote-debugging-port=0", "about:blank"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            port_file = Path(profile) / "DevToolsActivePort"
            deadline = time.monotonic() + 15
            while not port_file.is_file():
                if process.poll() is not None:
                    raise RuntimeError("Edge exited before starting its local debugging endpoint")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Edge startup timed out")
                time.sleep(0.1)
            port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
            env = {
                **os.environ,
                "PYTHONUTF8": "1",
                "PRACTICE05_PYTHON": sys.executable,
                "PRACTICE05_CDP_URL": f"http://127.0.0.1:{port}",
            }
            if args.playwright_module:
                env["PLAYWRIGHT_MODULE"] = args.playwright_module
            result = subprocess.run([args.node, "tests/e2e.cjs"], cwd=project, env=env,
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=90)
            output = result.stdout + result.stderr
            (project / "evidence/e2e-run.txt").write_text(output, encoding="utf-8")
            print(output, end="")
            return result.returncode
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
