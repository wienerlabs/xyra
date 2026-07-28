#!/usr/bin/env python3
"""Extract translatable UI string candidates from the Zed source.

Shares the file-walk / line-skip skeleton of rebrand-strings.py. Emits two kinds
of candidate: high-confidence UI call/assignment patterns (Label::new, .tooltip,
struct fields like title:/description:) and bare literals that pass a strict
UI-text filter. Output is translations/candidates.json, keyed by the verbatim
source literal with its source-file:line locations; tr.json is a translated
subset of these keys. Extraction need not be exact: extra candidates that are
not in tr.json are simply not translated (translate-strings.py is
location-restricted), and missing candidates can be added by hand.

Usage: extract-ui-strings.py [ZED_SRC] [OUT_JSON]
"""
import json
import os
import re
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.cache/xyra/zed-src")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO_DIR, "translations", "candidates.json")

EXCLUDE_DIR_PARTS = (
    "/collab/",
    "/windows",
    "/etw_tracing/",
    "/explorer_command_injector/",
    "/auto_update_helper/",
    "/examples/",
    "/fixtures/",
    "/migrator/",
    "/evals/",
    "/eval/",
    "_cli/",
    "_macros/",
    "/crashes/",
    "/system_specs/",
    "/telemetry_events/",
    "/rpc/",
    "/proto/",
    "/remote/",
    "/remote_server/",
    "/client/",
    "/cloud_api_types/",
    "/cloud_llm_client/",
    "/dap/",
    "/dap_adapters/",
    "/sqlez/",
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
    if stripped.startswith("//") or stripped.startswith("#["):
        return True
    if "telemetry::event!" in line or "event!(" in line:
        return True
    if any(marker in line for marker in TEST_MARKERS):
        return True
    if "font_names" in line or "icon_theme_names" in line:
        return True
    if "log::" in line or "eprintln!" in line or 'println!' in line:
        return True
    if any(m in line for m in (".expect(", "panic!", "unreachable!", "unimplemented!",
                               "todo!", "bail!", ".context(", "debug_assert")):
        return True
    if "assert" in line and "!" in line:
        return True
    return False


UI_PATTERNS = [
    re.compile(r'(?:Label|Headline|HighlightedLabel|Title)::new\s*\(\s*"'),
    re.compile(
        r'\.(?:tooltip_text|title|text|label|full_label|placeholder|placeholder_text'
        r'|description|subtitle|message|header|hint|set_text|set_placeholder|footer'
        r'|primary_message|secondary_message|detail|secondary_label|confirm_label'
        r'|dismiss_label|cancel_label|toast)\s*\(\s*"'
    ),
    re.compile(r'Tooltip::(?:text|with_meta)\s*\(\s*"'),
    re.compile(r'(?:Button|ToggleButton|IconButton)::new\s*\([^,()]+,\s*"'),
    re.compile(r'\.action\s*\(\s*"'),
    re.compile(
        r'\b(?:title|description|label|placeholder|message|tooltip|header|subtitle'
        r'|detail|hint|heading|caption|summary|help_text|error_message|empty_text'
        r'|empty_message|button_text|section_title|primary_label|secondary_label'
        r'|confirm_label|cancel_label|dismiss_label|action_label|status_message'
        r'|display_name|placeholder_text|subheading|prompt|note):\s*"'
    ),
]

STRING_LITERAL = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
URL_MARKERS = ("://", "github.com", "zed.dev", "www.", "https")
IDENT_LOWER = re.compile(r"[a-z0-9_]+")
IDENT_KEBAB = re.compile(r"[a-z0-9-]+")
LETTERS = re.compile(r"[A-Za-z]")
FIRST_ALPHA = re.compile(r"[A-Za-z]")


def looks_untranslatable(s):
    if not s or not s.strip():
        return True
    if any(m in s for m in URL_MARKERS):
        return True
    if not LETTERS.search(s):
        return True
    if " " not in s:
        if IDENT_LOWER.fullmatch(s) or IDENT_KEBAB.fullmatch(s):
            return True
        if "/" in s or ("." in s and not s.endswith((".", "...", "?", "!", ":"))):
            return True
    return False


def is_ui_text(s):
    if looks_untranslatable(s):
        return False
    if len(s) > 160:
        return False
    if any(c in s for c in ("::", "{", "}", "<", ">", "\\", "\t", "$")):
        return False
    m = FIRST_ALPHA.search(s)
    if not m or not m.group(0).isupper():
        return False
    return True


def extract_high_conf(line):
    out = []
    for pat in UI_PATTERNS:
        for m in pat.finditer(line):
            sm = STRING_LITERAL.match(line, m.end() - 1)
            if sm and not looks_untranslatable(sm.group(1)):
                out.append(sm.group(1))
    return out


def extract_bare(line):
    return [m.group(1) for m in STRING_LITERAL.finditer(line) if is_ui_text(m.group(1))]


def main():
    catalog = {}
    crates_root = os.path.join(SRC, "crates")
    if not os.path.isdir(crates_root):
        sys.exit(f"error: Zed source not found: {crates_root}")
    for root, _, files in os.walk(crates_root):
        for name in files:
            path = os.path.join(root, name)
            if not is_candidate(path):
                continue
            rel = os.path.relpath(path, SRC).replace("\\", "/")
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    if skip_line(line):
                        continue
                    for body in set(extract_high_conf(line)) | set(extract_bare(line)):
                        catalog.setdefault(body, []).append(f"{rel}:{i}")

    ordered = dict(sorted(catalog.items(), key=lambda kv: kv[0].lower()))
    out = {
        "_comment": (
            "Generated from Zed v1.10.3 by extract-ui-strings.py. Candidate UI string set "
            "(high-confidence patterns plus strict-filtered bare literals). Key = verbatim "
            "source literal; tr.json is a translated subset of these keys. Do not edit by "
            "hand - regenerate by running the script against the branded source."
        ),
        "zed_version": "v1.10.3",
        "count": len(ordered),
        "strings": ordered,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"extracted {len(ordered)} candidate UI strings -> {OUT}")


if __name__ == "__main__":
    main()
