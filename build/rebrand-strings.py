import os
import re
import sys

SRC = sys.argv[1]
APPLY = "--apply" in sys.argv

EXCLUDE_DIR_PARTS = (
    "/collab/",
    "/windows",
    "/etw_tracing/",
    "/explorer_command_injector/",
    "/auto_update_helper/",
    "/examples/",
)

EXCLUDE_FILE_SUFFIXES = ("_test.rs", "_tests.rs")

EXCLUDE_FILE_PARTS = (
    "gpui/src/text_system.rs",
    "settings/src/settings_store.rs",
    "paths/src/paths.rs",
)

CONTENT_KEEP = ("-Editor-", "Plex", "Zed Mono", "Zed Icons", "Zed Sans")

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
    if not path.endswith(".rs"):
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


STRING_LITERAL = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
ZED_WORD = re.compile(r'(?<![A-Za-z0-9_])Zed(?![A-Za-z0-9_])')

URL_MARKERS = ("://", ".dev", "github.com", ".nvim", "zed.dev")


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


def transform_string(body):
    if any(m in body for m in URL_MARKERS):
        return body
    if any(k in body for k in CONTENT_KEEP):
        return body
    if "Zed" not in body:
        return body
    return ZED_WORD.sub("Xyra", body)


def process(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    changed = []
    new_lines = []
    for i, line in enumerate(lines):
        if skip_line(line) or "Zed" not in line:
            new_lines.append(line)
            continue

        def repl(m):
            body = m.group(1)
            new_body = transform_string(body)
            return '"' + new_body + '"'

        new_line = STRING_LITERAL.sub(repl, line)
        if new_line != line:
            changed.append((i + 1, line.rstrip("\n"), new_line.rstrip("\n")))
        new_lines.append(new_line)
    if changed and APPLY:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    return changed


total = 0
files_touched = 0
for root, _, files in os.walk(os.path.join(SRC, "crates")):
    for name in files:
        path = os.path.join(root, name)
        if not is_candidate(path):
            continue
        changes = process(path)
        if changes:
            files_touched += 1
            total += len(changes)
            rel = os.path.relpath(path, SRC)
            for ln, old, new in changes:
                print(f"{rel}:{ln}")
                print(f"  - {old.strip()}")
                print(f"  + {new.strip()}")

print(f"\n{'APPLIED' if APPLY else 'DRY-RUN'}: {total} changes, {files_touched} files")
