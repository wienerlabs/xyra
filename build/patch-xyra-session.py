import sys

SRC = sys.argv[1]
path = f"{SRC}/crates/zed/src/main.rs"

ANCHOR = "fn main() {"
INSERT = """fn main() {
    unsafe { std::env::set_var("XYRA_SESSION", "1") };
"""

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

if "XYRA_SESSION" in content:
    print("xyra session marker already patched")
elif ANCHOR in content:
    content = content.replace(ANCHOR, INSERT, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("xyra session marker patched: every process started from Xyra is tagged")
else:
    print("warning: main.rs entry point not found, session marker skipped", file=sys.stderr)
