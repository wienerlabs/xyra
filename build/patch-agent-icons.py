import sys

SRC = sys.argv[1]
path = f"{SRC}/crates/agent_servers/src/custom.rs"

OLD = """    fn logo(&self) -> IconName {
        IconName::Terminal
    }"""

NEW = """    fn logo(&self) -> IconName {
        let id = self.agent_id.0.as_ref().to_lowercase();
        if id.contains("grok") {
            IconName::AiXAi
        } else if id.contains("claude") {
            IconName::AiClaude
        } else if id.contains("ollama") {
            IconName::AiOllama
        } else if id.contains("gemini") {
            IconName::AiGemini
        } else if id.contains("codex") || id.contains("openai") {
            IconName::AiOpenAi
        } else {
            IconName::Terminal
        }
    }"""

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

if NEW in content:
    print("agent ikon yaması zaten uygulanmış")
elif OLD in content:
    content = content.replace(OLD, NEW, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("agent ikon yaması uygulandı: Grok/Claude/Ollama marka logoları")
else:
    print("uyarı: custom.rs logo() beklenen biçimde değil, ikon yaması atlandı", file=sys.stderr)
