#!/usr/bin/env python3
"""Read-only code inspection for CTO, confined to the mounted target/ repository.

Usage: cto_inspect.py grep [-niwlcEFHIv...] PATTERN FILE...   (search the repo: git grep)
       cto_inspect.py head [-nN] FILE...      cto_inspect.py cat [-n] FILE...
       cto_inspect.py wc [-lwc] FILE...        cto_inspect.py ls [-laR1h] [PATH...]
       cto_inspect.py git <log|show|diff|grep|ls-files|blame> [flags] [REV|PATTERN...] [-- PATHSPEC...]

This is the only command CTO may run. Raw git/find/cat would let a prompt
injected through ticket text run commands (find -exec, git -c core.pager) or
read secrets outside target/ (/proc/1/environ, .local/openclaw.env). Flags are
allowlisted per command; anything unknown is refused. File contents are readable
only for git-tracked files, so ignored secrets inside target/ (.env, .local/)
stay out of reach whatever TARGET_REPO points at.
"""
import os
import re
import subprocess
import sys

TARGET = os.path.realpath(os.environ.get("CTO_TARGET", "/project/openclaw/workspace/agents/cto/target"))

# Flags that never take a file argument. Values only in attached `--x=value` form.
TOOL_FLAGS = {
    "grep": r"-[niwlcEFHhIv]+|--(line-number|ignore-case|count|files-with-matches)",
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
GIT_ENV = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_PAGER": "cat", "PAGER": "cat", "HOME": "/nonexistent"}


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


def check_tracked_files(paths):
    for path in paths:
        tracked = subprocess.run(["git", "-c", f"safe.directory={TARGET}", "-C", TARGET, "ls-files", "--error-unmatch",
                                  "--", path], env=GIT_ENV, capture_output=True)
        if tracked.returncode != 0 or not os.path.isfile(os.path.join(TARGET, path)):
            raise ValueError(f"not a git-tracked file (use git grep to search): {path}")


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
    if tool != "ls":
        check_tracked_files(paths)
    return [tool, *args], {"PATH": "/usr/bin:/bin"}


def check_git(args):
    if not args or args[0] not in GIT_FLAGS:
        raise ValueError("git subcommand must be one of: " + ", ".join(sorted(GIT_FLAGS)))
    sub, rest = args[0], args[1:]
    head, pathspecs = (rest[:rest.index("--")], rest[rest.index("--") + 1:]) if "--" in rest else (rest, [])
    _, operands = split_flags(head, GIT_FLAGS[sub])
    env = GIT_ENV
    # git grep takes the pattern first; every other pre-`--` operand must be a real revision,
    # so no operand can be read as a path (e.g. `git diff a.py ..` would switch to --no-index).
    revisions = operands[1:] if sub == "grep" else operands
    for rev in revisions:
        verified = subprocess.run(["git", "-C", TARGET, "rev-parse", "--verify", "--quiet", "--end-of-options",
                                   rev + "^{object}"], env=env, capture_output=True)
        if NO_REV.search(rev) or verified.returncode != 0:
            raise ValueError(f"not a revision (put paths after --): {rev}")
    check_paths(pathspecs)
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
