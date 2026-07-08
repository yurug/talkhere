#!/usr/bin/env python3
"""kb-lint — mechanical validation for agent-optimized knowledge bases.

The KB methodology (see spec-driven-dev) rests on properties that are
machine-checkable: files stay small, frontmatter triages, links resolve,
indexes route. This linter turns "the KB is maintained" from a hope into
an exit code. Wire it into pre-commit and CI; errors fail the build.

Usage:
    kb-lint.py [KB_DIR] [--strict] [--no-git] [--required-keys k1,k2,...]

    KB_DIR            defaults to ./kb
    --strict          treat warnings as errors
    --no-git          skip git-based staleness checks
    --required-keys   override the required frontmatter keys
                      (use "id,domain,last-updated" for pre-2026 KBs
                      that lack type/summary)

Exit code: 0 = clean (warnings allowed), 1 = errors (or warnings with --strict).

Checks (E = error, W = warning):
    E-frontmatter   missing or unparseable frontmatter block
    E-key           missing required frontmatter key
    E-type          `type` not in the closed set
    E-date          `last-updated` not a real YYYY-MM-DD date
    E-dup-id        duplicate `id` across the KB
    E-link          markdown/backtick link to a KB .md path that does not exist
    E-id-ref        depends-on/refines/related names an id that no file declares
    E-length        file exceeds max lines (default 200; override with
                    `lint-max-lines: N` in frontmatter, which documents the
                    exception where reviewers will see it)
    E-index         directory holding 2+ md files has no INDEX.md
    W-stale         last git commit of the file is newer than `last-updated`
    W-dirty         file has uncommitted changes but `last-updated` is not today
    W-orphan        no other file links to this one (unreachable from the graph)
    W-bare-link     bare-filename backtick ref that resolves nowhere

Exempt from all checks (but still valid link targets): reports/ (generated
artifacts) and questions-round*.md (working files edited by the user).
"""

import argparse
import datetime
import os
import re
import subprocess
import sys

TYPE_SET = {"concept", "decision", "constraint", "procedure", "spec",
            "external", "index", "glossary"}
DEFAULT_REQUIRED = ["id", "type", "summary", "domain", "last-updated"]
DEFAULT_MAX_LINES = 200
ID_REF_KEYS = ("depends-on", "refines", "related")

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
BACKTICK_RE = re.compile(r"`([^`\s]+\.md(?:#[^`]*)?)`")
FENCE_RE = re.compile(r"^(```|~~~)", re.MULTILINE)


def is_exempt(relpath):
    parts = relpath.split(os.sep)
    return parts[0] == "reports" or \
        re.match(r"questions-round.*\.md$", parts[-1]) is not None


def parse_frontmatter(text):
    """Return (dict, error). Naive YAML: `key: scalar` and `key: [a, b]` only."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "no frontmatter block (file must start with ---)"
    fm = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return fm, None
        line = line.split("#", 1)[0].rstrip()  # strip trailing comments
        if not line.strip():
            continue
        if ":" not in line:
            return None, f"frontmatter line {i + 1} is not `key: value`"
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("'\"") for v in value[1:-1].split(",")]
            fm[key] = [v for v in items if v]
        else:
            fm[key] = value.strip("'\"")
    return None, "frontmatter block never closed with ---"


def strip_fences(text):
    """Blank out fenced code blocks so example paths inside them are not linted."""
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
        else:
            out.append("" if in_fence else line)
    return "\n".join(out)


def extract_links(text):
    """Yield (target, bare) for every KB-file reference in prose.

    Globs (`spec/*.md`) and placeholders (`<name>.md`, `YYYY-MM-DD`) are
    patterns, not links — skip them rather than flag them.
    """
    def is_pattern(t):
        return any(c in t for c in "*<>") or "YYYY" in t

    body = strip_fences(text)
    for m in MD_LINK_RE.finditer(body):
        t = m.group(1).split("#", 1)[0].strip()
        if t and not t.startswith(("http://", "https://", "mailto:")) \
                and t.endswith(".md") and not is_pattern(t):
            yield t, False
    for m in BACKTICK_RE.finditer(body):
        t = m.group(1).split("#", 1)[0].strip()
        if t and not t.startswith(("http://", "https://")) and not is_pattern(t):
            # A bare filename (`INDEX.md`) is a weaker claim than a path.
            yield t, "/" not in t


def git_dates(kb_dir, relpath):
    """Return (last_commit_date, is_dirty) or (None, None) if not in git."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=short", "--", relpath],
            cwd=kb_dir, capture_output=True, text=True, timeout=10)
        commit = out.stdout.strip() or None
        st = subprocess.run(
            ["git", "status", "--porcelain", "--", relpath],
            cwd=kb_dir, capture_output=True, text=True, timeout=10)
        return commit, bool(st.stdout.strip())
    except Exception:
        return None, None


def main():
    ap = argparse.ArgumentParser(
        description="Mechanical validation for agent-optimized knowledge bases.")
    ap.add_argument("kb_dir", nargs="?", default="kb")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--required-keys", default=",".join(DEFAULT_REQUIRED))
    args = ap.parse_args()
    required = [k.strip() for k in args.required_keys.split(",") if k.strip()]

    kb = os.path.abspath(args.kb_dir)
    if not os.path.isdir(kb):
        print(f"kb-lint: no such directory: {kb}", file=sys.stderr)
        return 2

    errors, warnings = [], []
    files = {}       # relpath -> (frontmatter, text)
    ids = {}         # id -> relpath
    linked_to = set()

    for root, dirs, names in os.walk(kb):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in sorted(names):
            if name.endswith(".md"):
                rel = os.path.relpath(os.path.join(root, name), kb)
                with open(os.path.join(kb, rel), encoding="utf-8") as f:
                    files[rel] = f.read()

    today = datetime.date.today().isoformat()

    for rel, text in sorted(files.items()):
        # Exempt files (reports, question rounds) are historical artifacts:
        # their links legitimately rot as the KB evolves, so skip them fully.
        if is_exempt(rel):
            continue

        for target, bare in extract_links(text):
            cands = [os.path.normpath(os.path.join(os.path.dirname(rel), target)),
                     os.path.normpath(target)]
            hit = next((c for c in cands if c in files), None)
            if hit:
                linked_to.add(hit)
            elif bare:
                warnings.append((rel, f"W-bare-link: `{target}` resolves nowhere"))
            else:
                # The target escapes the KB: resolve on the filesystem,
                # relative to the file's own directory and to the repo root.
                fs_cands = [os.path.join(kb, os.path.dirname(rel), target),
                            os.path.join(kb, "..", target)]
                if not any(os.path.exists(os.path.normpath(c)) for c in fs_cands):
                    errors.append((rel, f"E-link: `{target}` does not exist"))

        fm, err = parse_frontmatter(text)
        if fm is None:
            errors.append((rel, f"E-frontmatter: {err}"))
            fm = {}
        for key in required:
            if key not in fm:
                errors.append((rel, f"E-key: missing `{key}` in frontmatter"))
        if "type" in fm and "type" in required and fm["type"] not in TYPE_SET:
            errors.append((rel, f"E-type: `{fm['type']}` not in {sorted(TYPE_SET)}"))
        if "id" in fm:
            if fm["id"] in ids:
                errors.append((rel, f"E-dup-id: `{fm['id']}` also declared "
                                    f"in {ids[fm['id']]}"))
            else:
                ids[fm["id"]] = rel

        lu = fm.get("last-updated", "")
        if "last-updated" in fm and "last-updated" in required:
            try:
                datetime.date.fromisoformat(lu)
            except ValueError:
                errors.append((rel, f"E-date: last-updated `{lu}` is not YYYY-MM-DD"))
                lu = ""

        max_lines = int(fm.get("lint-max-lines", DEFAULT_MAX_LINES))
        n = text.count("\n") + 1
        if n > max_lines:
            errors.append((rel, f"E-length: {n} lines > {max_lines} "
                                "(split the file, or document the exception "
                                "with `lint-max-lines: N`)"))

        if not args.no_git and lu:
            commit, dirty = git_dates(kb, rel)
            if commit and commit > lu:
                warnings.append((rel, f"W-stale: last commit {commit} is newer "
                                      f"than last-updated {lu}"))
            if dirty and lu != today:
                warnings.append((rel, f"W-dirty: uncommitted changes but "
                                      f"last-updated is {lu}, not {today}"))

    # -- id references resolve only after every id is known.
    for rel, text in sorted(files.items()):
        if is_exempt(rel):
            continue
        fm, _ = parse_frontmatter(text)
        if not fm:
            continue
        for key in ID_REF_KEYS:
            refs = fm.get(key, [])
            if isinstance(refs, str):
                refs = [refs] if refs else []
            for ref in refs:
                if ref and ref not in ids:
                    errors.append((rel, f"E-id-ref: {key} names unknown id `{ref}`"))

    # -- every directory with 2+ md files needs a routing table.
    for root, dirs, names in os.walk(kb):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel = os.path.relpath(root, kb)
        if rel != "." and is_exempt(os.path.join(rel, "x.md")):
            continue
        mds = [n for n in names if n.endswith(".md")]
        if len(mds) >= 2 and "INDEX.md" not in mds:
            errors.append((rel if rel != "." else "kb/",
                           "E-index: directory holds 2+ md files but no INDEX.md"))

    # -- orphans: unreachable files defeat the routing-table design.
    for rel in sorted(files):
        if rel == "INDEX.md" or is_exempt(rel):
            continue
        if rel not in linked_to:
            warnings.append((rel, "W-orphan: no other KB file links here"))

    for rel, msg in errors:
        print(f"ERROR {rel}: {msg}")
    for rel, msg in warnings:
        print(f"WARN  {rel}: {msg}")
    print(f"kb-lint: {len(files)} files, {len(errors)} errors, "
          f"{len(warnings)} warnings")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
