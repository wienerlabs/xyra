#!/usr/bin/env python3
"""Apply build-time English->localized UI translation to the Xyra source.

Shares the file-walk / string-literal skeleton of rebrand-strings.py, with two
differences: it looks up each literal in translations/<lang>.json instead of
transforming it, and it only translates a literal at a UI location recorded for
that literal in candidates.json (occurrence-restricted), so short words are not
translated in non-UI contexts. Called from patch-brand.sh after the brand
rebrand, guarded by XYRA_LANG; with XYRA_LANG unset the English build is untouched.

Usage:
  translate-strings.py <ZED_SRC> [--lang tr] [--apply]
    Without --apply it runs a dry run: it counts changes without writing.
"""
import json
import os
import re
import sys


def die(msg):
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


ARGS = sys.argv[1:]
if not ARGS or ARGS[0].startswith("-"):
    die("usage: translate-strings.py <ZED_SRC> [--lang tr] [--apply]")
SRC = ARGS[0]
APPLY = "--apply" in ARGS
LANG = "tr"
if "--lang" in ARGS:
    idx = ARGS.index("--lang")
    if idx + 1 < len(ARGS):
        LANG = ARGS[idx + 1]

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(REPO_DIR, "translations", f"{LANG}.json")
GLOSSARY_PATH = os.path.join(REPO_DIR, "translations", f"glossary.{LANG}.json")
CANDIDATES_PATH = os.path.join(REPO_DIR, "translations", "candidates.json")

EXCLUDE_DIR_PARTS = (
    "/collab/",
    "/windows",
    "/etw_tracing/",
    "/explorer_command_injector/",
    "/auto_update_helper/",
    "/examples/",
    "/migrator/",
)
EXCLUDE_FILE_SUFFIXES = ("_test.rs", "_tests.rs")
EXCLUDE_FILE_PARTS = (
    "gpui/src/text_system.rs",
    "settings/src/settings_store.rs",
    "paths/src/paths.rs",
)
TEST_MARKERS = (
    "assert_eq!",
    "assert_state",
    "set_state",
    "simulate_",
    "indoc!",
    "assert!(",
    "expected",
)


def is_candidate(path):
    path = path.replace("\\", "/")
    if not path.endswith(".rs"):
        return False
    if path.rsplit("/", 1)[-1] == "build.rs":
        return False
    if any(path.endswith(sfx) for sfx in EXCLUDE_FILE_SUFFIXES):
        return False
    if "/tests/" in path or "/test/" in path:
        return False
    if any(part in path for part in EXCLUDE_DIR_PARTS):
        return False
    if any(part in path for part in EXCLUDE_FILE_PARTS):
        return False
    return True


def skip_line(line):
    stripped = line.lstrip()
    if stripped.startswith("//"):
        return True
    if "telemetry::event!" in line or "event!(" in line:
        return True
    if any(marker in line for marker in TEST_MARKERS):
        return True
    if "font_names" in line or "icon_theme_names" in line:
        return True
    return False


STRING_LITERAL = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
PLACEHOLDER = re.compile(r"\{[^{}]*\}")

SERDE_CTX = re.compile(r"#\[derive\([^)]*\b(?:Serialize|Deserialize)\b|#\[serde\(")
ACTION_CTX = re.compile(r"register_action|actions!\(|impl_actions!|gpui::actions|#\[action")
SCHEMA_CTX = re.compile(r"JsonSchema|schemars|#\[schema")
KEYMAP_CTX = re.compile(r"KeyContext|key_context|action_query")
ENV_MACRO = re.compile(r"\benv!|\boption_env!|\binclude_str!|\binclude_bytes!|\binclude!|\bconcat!|\bcfg!\(")
KEYCTX_DISPATCH = re.compile(r"KeyContext|key_context|dispatch_context|DispatchContext")
KEYCTX_ADD = re.compile(r'\.\s*(?:add|set|insert)\s*\(\s*"')


def is_unsafe_line(rel, lines, lineno, line):
    if "_macros/" in rel or "settings_content/" in rel:
        return True
    stripped = line.lstrip()
    if stripped.startswith("#["):
        return True
    if ENV_MACRO.search(line) or ACTION_CTX.search(line) or KEYMAP_CTX.search(line):
        return True
    if KEYCTX_ADD.search(line):
        kblock = "".join(lines[max(0, lineno - 16):min(len(lines), lineno + 2)])
        if KEYCTX_DISPATCH.search(kblock):
            return True
    block = "".join(lines[max(0, lineno - 13):min(len(lines), lineno + 2)])
    if SERDE_CTX.search(block) or SCHEMA_CTX.search(block) or "macro_rules!" in block:
        return True
    return False


if not os.path.isfile(CATALOG_PATH):
    die(f"translation catalog not found: {CATALOG_PATH}")
with open(CATALOG_PATH, encoding="utf-8") as fh:
    TRANSLATIONS = json.load(fh).get("translations", {})

KEEP = set()
if os.path.isfile(GLOSSARY_PATH):
    with open(GLOSSARY_PATH, encoding="utf-8") as fh:
        KEEP = set(json.load(fh).get("keep", []))

if not os.path.isfile(CANDIDATES_PATH):
    die(f"candidates.json not found (required for UI locations): {CANDIDATES_PATH}")
with open(CANDIDATES_PATH, encoding="utf-8") as fh:
    _cand = json.load(fh).get("strings", {})
OCCUR = {body: set(locs) for body, locs in _cand.items()}

STATS = {"files": 0, "translated": 0, "skipped_placeholder": 0}
USED = set()


def translation_for(body):
    if body in KEEP:
        return None
    tr = TRANSLATIONS.get(body)
    if tr is None:
        return None
    if set(PLACEHOLDER.findall(body)) != set(PLACEHOLDER.findall(tr)):
        STATS["skipped_placeholder"] += 1
        sys.stderr.write(f"  placeholder mismatch, skipped: {body!r} -> {tr!r}\n")
        return None
    return tr


def raw_string_mask(lines):
    text = "".join(lines)
    masked = set()
    for m in re.finditer(r'(?<![A-Za-z0-9_])b?r(#*)"', text):
        close = text.find('"' + m.group(1), m.end())
        if close < 0:
            continue
        start_ln = text.count("\n", 0, m.start()) + 1
        end_ln = text.count("\n", 0, close) + 1
        masked.update(range(start_ln, end_ln + 1))
    return masked


def process(path, rel):
    with open(path, encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()
    changed = 0
    new_lines = []
    raw_lines = raw_string_mask(lines)
    for lineno, line in enumerate(lines, 1):
        if lineno in raw_lines or skip_line(line) or is_unsafe_line(rel, lines, lineno, line):
            new_lines.append(line)
            continue

        def repl(m):
            nonlocal changed
            body = m.group(1)
            if f"{rel}:{lineno}" not in OCCUR.get(body, ()):
                return m.group(0)
            if "&&" in body or "||" in body:
                return m.group(0)
            after = line[m.end():].lstrip()
            if after.startswith("=>"):
                return m.group(0)
            if after.startswith(":"):
                return m.group(0)
            before = line[:m.start()].rstrip()
            if before.endswith((".get(", ".get_mut(", ".contains_key(", ".remove(")):
                return m.group(0)
            if before.endswith((".starts_with(", ".ends_with(", ".strip_prefix(", ".strip_suffix(")):
                return m.group(0)
            if before.endswith((".contains(", ".find(", ".rfind(", ".split(", ".splitn(",
                                ".rsplit(", ".split_once(", ".rsplit_once(", ".contains_str(")):
                return m.group(0)
            if before.endswith((".header(", ".set_header(", ".append_header(", ".insert_header(", ".typed_header(")) \
                    and after.startswith(","):
                return m.group(0)
            i = m.start()
            if line[i - 1:i] == "b" or line[max(0, i - 2):i] in ("rb", "br", "bR", "rB"):
                return m.group(0)
            tr = translation_for(body)
            if tr is None or tr == body:
                return m.group(0)
            changed += 1
            USED.add(body)
            return '"' + tr + '"'

        new_lines.append(STRING_LITERAL.sub(repl, line))
    if changed and APPLY:
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(new_lines)
    return changed


def main():
    crates_root = os.path.join(SRC, "crates")
    if not os.path.isdir(crates_root):
        die(f"Zed source not found: {crates_root}")
    for root, _, files in os.walk(crates_root):
        for name in files:
            path = os.path.join(root, name)
            if not is_candidate(path):
                continue
            rel = os.path.relpath(path, SRC).replace("\\", "/")
            count = process(path, rel)
            if count:
                STATS["files"] += 1
                STATS["translated"] += count

    unused = sorted(k for k in TRANSLATIONS if k not in USED)
    mode = "APPLIED" if APPLY else "DRY-RUN"
    print(
        f"{mode} [{LANG}]: {STATS['translated']} strings translated, "
        f"{STATS['files']} files | catalog {len(TRANSLATIONS)}, "
        f"unapplied {len(unused)}, placeholder-skipped {STATS['skipped_placeholder']}"
    )
    if unused and not APPLY:
        sys.stderr.write(
            "  note: the following catalog keys were never applied "
            "(not found in source/location - version or extraction drift):\n"
        )
        for k in unused[:20]:
            sys.stderr.write(f"    {k!r}\n")
        if len(unused) > 20:
            sys.stderr.write(f"    ... (+{len(unused) - 20})\n")


if __name__ == "__main__":
    main()
