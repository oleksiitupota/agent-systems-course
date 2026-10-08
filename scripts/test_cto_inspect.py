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
        Path(target, ".env").write_text("TOKEN=ignored-secret\n")  # untracked secret inside target/
        os.symlink(os.path.join(root, "secret.env"), os.path.join(target, "link"))
        subprocess.run(["git", "init", "-q", target], check=True)
        subprocess.run(["git", "-C", target, "add", "a.py"], check=True)
        subprocess.run(["git", "-C", target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "-m", "init"], check=True)

        assert run(target, "grep", "-n", "token", "a.py").stdout.strip() == "1:token = 1"
        assert run(target, "head", "-n1", "a.py").returncode == 0
        assert run(target, "head", "-n", "1", "a.py").stdout.strip() == "token = 1"
        assert run(target, "git", "grep", "-n", "token").stdout.strip() == "a.py:1:token = 1"
        assert run(target, "git", "ls-files").returncode == 0
        assert run(target, "git", "log", "--oneline", "-5", "--", "a.py").returncode == 0
        assert run(target, "git", "show", "--stat", "HEAD").returncode == 0
        assert run(target, "git", "grep", "-n", "token", "HEAD").returncode in (0, 1)
        refused = [
            ("cat", "../secret.env"), ("cat", "/proc/1/environ"), ("cat", "link"),
            ("grep", "-r", "SECRET", ".."), ("grep", "-R", "SECRET", "."), ("grep", "-rn", "TOKEN", "."),
            ("grep", "-n", "TOKEN", ".env"), ("cat", ".env"), ("head", "-n1", ".env"), ("head", "-n", "1", ".env"), ("head", "-n", "../secret.env"), ("grep", "x", "."), ("grep", "-f", "../secret.env", "a.py"), ("grep", "x"),
            ("find", ".", "-exec", "id", ";"), ("sh", "-c", "id"),
            ("git", "-c", "core.pager=id", "log"), ("git", "log", "-c", "x=y"),
            ("git", "grep", "-Oid", "x"), ("git", "fetch", "--upload-pack=id"), ("git", "config", "-l"),
            ("grep", "-ex", "/proc/1/environ", "a.py"), ("grep", "-e", "x", "a.py"),
            ("grep", "--files0-from=../secret.env", "x", "a.py"), ("head", "-c", "9", "/proc/1/environ"),
            ("git", "diff", "--no-index", "/proc/1/environ", "/dev/null"),
            ("git", "blame", "--contents", "../secret.env", "a.py"), ("git", "log", "--", "../secret.env"),
            ("git", "show", "--output=../x"), ("git", "log", "../secret.env"),
            ("git", "diff", "a.py", ".."), ("git", "diff", "a.py", "x/../.."), ("git", "log", "a.py"),
        ]
        for args in refused:
            result = run(target, *args)
            assert result.returncode != 0 and "cto_inspect refused" in result.stderr, (args, result)
    print("cto_inspect: ok")
