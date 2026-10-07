#!/usr/bin/env python3
"""Read-only code inspection for CTO, confined to the mounted target/ repository.

Usage: cto_inspect.py grep [-rniwlcEFHIv...] [--include=GLOB] PATTERN PATH...
       cto_inspect.py head [-nN] PATH...      cto_inspect.py cat [-n] PATH...
       cto_inspect.py wc [-lwc] PATH...        cto_inspect.py ls [-laR1h] [PATH...]
       cto_inspect.py git <log|show|diff|grep|ls-files|blame> [flags] [REV|PATTERN...] [-- PATHSPEC...]

This is the only command CTO may run. Raw git/find/cat would let a prompt
injected through ticket text run commands (find -exec, git -c core.pager) or
read secrets outside target/ (/proc/1/environ, .local/openclaw.env). Flags are
allowlisted per command; anything unknown is refused.
"""
import os
import re
import subprocess
import sys

TARGET = os.path.realpath(os.environ.get("CTO_TARGET", "/project/openclaw/workspace/agents/cto/target"))

# Flags that never take a file argument. Values only in attached `--x=value` form.
TOOL_FLAGS = {
    "grep": r"-[rniwlcEFHhIv]+|--(include|exclude|exclude-dir)=[^/]+|--(line-number|ignore-case|recursive|count|files-with-matches)",
    "head": r"-n\d+|-\d+",
    "cat": r"-n",
    "wc": r"-[lwc]+",
    "ls": r"-[laR1h]+",
}
GIT_FLAGS = {
    "log": r"--oneline|--stat|--name-only|-p|-\d+|-n\d+|--(format|pretty|since|until|author|grep)=[^\n]*",
    "show": r"--stat|--name-only|-p|--(format|pretty)=[^\n]*",
    "diff": r"--stat|--name-only|--cached",
    "grep": r"-[niwlcEFIv]+",
    "ls-files": r"",
    "blame": r"-L\d+(,\d+)?",
}
NO_REV = re.compile(r"^[-:]|\.\.\/|^/")  # revisions/patterns may not look like options or outside paths


def inside(path):
    real = os.path.realpath(os.path.join(TARGET, path))
    return real == TARGET or real.startswith(TARGET + os.sep)


def split_flags(args, pattern):
    flags, operands = [], []
    for arg in args:
        if arg.startswith("-"):
            if not pattern or not re.fullmatch(pattern, arg):
                raise ValueError(f"flag not allowed: {arg}")
            flags.append(arg)
        else:
            operands.append(arg)
    return flags, operands


def check_paths(paths):
    for path in paths:
        if not inside(path):
            raise ValueError(f"path outside target/: {path}")


def check_tool(tool, args):
    _, operands = split_flags(args, TOOL_FLAGS[tool])
    paths = operands
    if tool == "grep":
        if len(operands) < 2:
            raise ValueError("grep needs PATTERN and at least one PATH inside target/")
        paths = operands[1:]
    elif tool != "ls" and not operands:
        raise ValueError(f"{tool} needs at least one PATH inside target/")
    check_paths(paths)
    return [tool, *args], {"PATH": "/usr/bin:/bin"}


def check_git(args):
    if not args or args[0] not in GIT_FLAGS:
        raise ValueError("git subcommand must be one of: " + ", ".join(sorted(GIT_FLAGS)))
    sub, rest = args[0], args[1:]
    head, pathspecs = (rest[:rest.index("--")], rest[rest.index("--") + 1:]) if "--" in rest else (rest, [])
    _, operands = split_flags(head, GIT_FLAGS[sub])
    for operand in operands:
        if NO_REV.search(operand):
            raise ValueError(f"put paths after --: {operand}")
    check_paths(pathspecs)
    env = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_PAGER": "cat", "PAGER": "cat", "HOME": "/nonexistent"}
    return ["git", "--no-pager", "-c", f"safe.directory={TARGET}", "-C", TARGET, *args], env


def build(argv):
    if not argv:
        raise ValueError(__doc__)
    tool, args = argv[0], argv[1:]
    if tool == "git":
        return check_git(args)
    if tool in TOOL_FLAGS:
        return check_tool(tool, args)
    raise ValueError(f"command not allowed: {tool}")


if __name__ == "__main__":
    try:
        command, env = build(sys.argv[1:])
    except ValueError as error:
        sys.exit(f"cto_inspect refused: {error}")
    sys.exit(subprocess.run(command, cwd=TARGET, env=env).returncode)
