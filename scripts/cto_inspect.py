#!/usr/bin/env python3
"""Read-only code inspection for CTO, confined to the mounted target/ repository.

Usage: cto_inspect.py git <log|show|diff|grep|ls-files|blame> [args...]
       cto_inspect.py <grep|head|cat|wc|ls> [options] [args...]

This is the only command CTO may run. Raw git/find/cat would let a prompt
injected through ticket text run commands (find -exec, git -c core.pager) or
read secrets outside target/ (/proc/1/environ, .local/openclaw.env).
"""
import os
import subprocess
import sys

TARGET = os.path.realpath(os.environ.get("CTO_TARGET", "/project/openclaw/workspace/agents/cto/target"))
GIT_SUBCOMMANDS = {"log", "show", "diff", "grep", "ls-files", "blame"}
GIT_BLOCKED = ("-c", "--upload-pack", "--exec-path", "--config-env", "-O", "--open-files-in-pager",
               "--ext-diff", "--output", "--git-dir", "--work-tree", "-C")
TOOLS = {"grep", "head", "cat", "wc", "ls"}
TOOL_BLOCKED = ("-f", "--file", "--exclude-from", "--include-from")


def inside(path):
    real = os.path.realpath(os.path.join(TARGET, path))
    return real == TARGET or real.startswith(TARGET + os.sep)


def check_git(args):
    if not args or args[0] not in GIT_SUBCOMMANDS:
        raise ValueError("git subcommand must be one of: " + ", ".join(sorted(GIT_SUBCOMMANDS)))
    for arg in args[1:]:
        if arg.startswith(GIT_BLOCKED):
            raise ValueError(f"git option not allowed: {arg}")
    env = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_PAGER": "cat", "PAGER": "cat", "HOME": "/nonexistent"}
    return ["git", "--no-pager", "-c", f"safe.directory={TARGET}", "-C", TARGET, *args], env


def check_tool(tool, args):
    operands = [a for a in args if not a.startswith("-")]
    for arg in args:
        if arg.startswith(TOOL_BLOCKED):
            raise ValueError(f"{tool} option not allowed: {arg}")
    # grep's first operand is the pattern, not a path.
    paths = operands[1:] if tool == "grep" else operands
    if tool == "grep" and not paths:
        raise ValueError("grep needs at least one path inside target/")
    for path in paths:
        if not inside(path):
            raise ValueError(f"path outside target/: {path}")
    return [tool, *args], {"PATH": "/usr/bin:/bin"}


def build(argv):
    if not argv:
        raise ValueError(__doc__)
    tool, args = argv[0], argv[1:]
    if tool == "git":
        return check_git(args)
    if tool in TOOLS:
        return check_tool(tool, args)
    raise ValueError(f"command not allowed: {tool}")


if __name__ == "__main__":
    try:
        command, env = build(sys.argv[1:])
    except ValueError as error:
        sys.exit(f"cto_inspect refused: {error}")
    sys.exit(subprocess.run(command, cwd=TARGET, env=env).returncode)
