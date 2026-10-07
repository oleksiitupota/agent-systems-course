"""Check that scripts/cto_inspect.py stays inside target/ and blocks command execution."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("cto_inspect.py")


def run(target, *args):
    env = {**os.environ, "CTO_TARGET": target}
    return subprocess.run([sys.executable, SCRIPT, *args], cwd=target, env=env, capture_output=True, text=True)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as root:
        target = os.path.join(root, "target")
        os.mkdir(target)
        Path(target, "a.py").write_text("token = 1\n")
        Path(root, "secret.env").write_text("SECRET=1\n")
        os.symlink(os.path.join(root, "secret.env"), os.path.join(target, "link"))
        subprocess.run(["git", "init", "-q", target], check=True)

        assert run(target, "grep", "-n", "token", "a.py").stdout.strip() == "1:token = 1"
        assert run(target, "head", "-n", "1", "a.py").returncode == 0
        assert run(target, "git", "ls-files").returncode == 0
        refused = [
            ("cat", "../secret.env"), ("cat", "/proc/1/environ"), ("cat", "link"),
            ("grep", "-r", "SECRET", ".."), ("grep", "-f", "../secret.env", "a.py"), ("grep", "x"),
            ("find", ".", "-exec", "id", ";"), ("sh", "-c", "id"),
            ("git", "-c", "core.pager=id", "log"), ("git", "log", "-c", "x=y"),
            ("git", "grep", "-Oid", "x"), ("git", "fetch", "--upload-pack=id"), ("git", "config", "-l"),
        ]
        for args in refused:
            result = run(target, *args)
            assert result.returncode != 0 and "cto_inspect refused" in result.stderr, (args, result)
    print("cto_inspect: ok")
