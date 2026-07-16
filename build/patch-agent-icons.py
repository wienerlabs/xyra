import sys

SRC = sys.argv[1]


def brand_expr(src, fallback, indent):
    pad = " " * indent
    return (
        f"if {src}.contains(\"grok\") {{\n"
        f"{pad}    IconName::AiXAi\n"
        f"{pad}}} else if {src}.contains(\"claude\") {{\n"
        f"{pad}    IconName::AiClaude\n"
        f"{pad}}} else if {src}.contains(\"ollama\") {{\n"
        f"{pad}    IconName::AiOllama\n"
        f"{pad}}} else if {src}.contains(\"gemini\") {{\n"
        f"{pad}    IconName::AiGemini\n"
        f"{pad}}} else if {src}.contains(\"codex\") || {src}.contains(\"openai\") {{\n"
        f"{pad}    IconName::AiOpenAi\n"
        f"{pad}}} else {{\n"
        f"{pad}    IconName::{fallback}\n"
        f"{pad}}}"
    )


CUSTOM_NEW = (
    "    fn logo(&self) -> IconName {\n"
    "        let id = self.agent_id.0.as_ref().to_lowercase();\n"
    "        " + brand_expr("id", "Terminal", 8) + "\n"
    "    }"
)

PANEL_NEW = (
    "                                } else {\n"
    "                                    let key = item.display_name.to_lowercase();\n"
    "                                    let brand = " + brand_expr("key", "Sparkle", 36) + ";\n"
    "                                    entry = entry.icon(brand);\n"
    "                                }"
)

PATCHES = [
    {
        "path": f"{SRC}/crates/agent_servers/src/custom.rs",
        "old": "    fn logo(&self) -> IconName {\n        IconName::Terminal\n    }",
        "new": CUSTOM_NEW,
        "marker": "let id = self.agent_id.0.as_ref().to_lowercase();",
        "label": "agent thread icon",
    },
    {
        "path": f"{SRC}/crates/agent_ui/src/agent_panel.rs",
        "old": "                                } else {\n                                    entry = entry.icon(IconName::Sparkle);\n                                }",
        "new": PANEL_NEW,
        "marker": "let key = item.display_name.to_lowercase();",
        "label": "agent picker icon",
    },
]

for p in PATCHES:
    try:
        with open(p["path"], "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        continue
    if p["marker"] in content:
        print(f"{p['label']} patch already applied")
    elif p["old"] in content:
        content = content.replace(p["old"], p["new"], 1)
        with open(p["path"], "w", encoding="utf-8") as f:
            f.write(content)
        print(f"{p['label']} patch applied")
    else:
        print(f"warning: {p['path']} not in the expected shape, {p['label']} skipped", file=sys.stderr)
