"""Portable desktop launcher: python run.py [--install-only] [--reinstall]."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--reinstall", action="store_true")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5001")))
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("Python 3.10+ is required; Python 3.11 is recommended.")
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")

    root = Path(__file__).resolve().parent
    env_dir = root / ".venv"
    python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("Creating local virtual environment...", flush=True)
        venv.EnvBuilder(with_pip=True).create(env_dir)

    subprocess.run(
        [str(python), "-c",
         "import sys; assert sys.version_info >= (3, 10), "
         "'Existing .venv is too old. Rename it and run the launcher again.'"],
        check=True, cwd=root,
    )
    requirements = root / "requirements.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = env_dir / ".requirements.sha256"
    if args.reinstall or not marker.exists() or marker.read_text().strip() != fingerprint:
        print("Installing dependencies (internet access required)...", flush=True)
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(requirements)],
            check=True, cwd=root,
        )
        subprocess.run([str(python), "-m", "pip", "check"], check=True, cwd=root)
        marker.write_text(fingerprint, encoding="ascii")
    if args.install_only:
        print("Installation complete.")
        return

    env = dict(os.environ, HOST=args.host, PORT=str(args.port))
    print(f"Starting Snap-Solver Voice at http://localhost:{args.port}", flush=True)
    try:
        result = subprocess.run([str(python), str(root / "app.py")], cwd=root, env=env)
        raise SystemExit(result.returncode)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
