import sys

SRC = sys.argv[1]

defaults_path = f"{SRC}/assets/settings/default.json"
DEFAULTS_ANCHOR = '  "agent_servers": {},'
DEFAULTS_INSERT = """  "agent_servers": {
    "Grok Build": {
      "type": "custom",
      "command": "grok",
      "args": ["agent", "stdio"],
      "env": {}
    }
  },"""

with open(defaults_path, "r", encoding="utf-8") as f:
    defaults = f.read()

if '"Grok Build"' in defaults:
    print("default agent servers already patched")
elif DEFAULTS_ANCHOR in defaults:
    defaults = defaults.replace(DEFAULTS_ANCHOR, DEFAULTS_INSERT, 1)
    with open(defaults_path, "w", encoding="utf-8") as f:
        f.write(defaults)
    print("default agent servers patched: Grok Build ships in the + menu on every OS")
else:
    print("warning: default.json agent_servers anchor not found, skipped", file=sys.stderr)

welcome_path = f"{SRC}/crates/workspace/src/welcome.rs"
WELCOME_ANCHOR = """                    .when(!self.fallback_to_recent_projects, |this| {
                        this.child(
                            v_flex().gap_4().child(Divider::horizontal()).child(
                                Button::new("welcome-exit", "Return to Onboarding")"""
WELCOME_INSERT = """                    .child({
                        let grok_home = std::env::var("HOME")
                            .or_else(|_| std::env::var("USERPROFILE"))
                            .unwrap_or_default();
                        let signed_in = std::fs::read_to_string(
                            std::path::Path::new(&grok_home).join(".grok").join("auth.json"),
                        )
                        .map(|contents| contents.contains("refresh_token"))
                        .unwrap_or(false);
                        v_flex()
                            .gap_4()
                            .child(Divider::horizontal())
                            .child(if signed_in {
                                h_flex()
                                    .w_full()
                                    .justify_center()
                                    .child(
                                        Label::new("Grok: signed in and ready")
                                            .size(LabelSize::Small)
                                            .color(Color::Muted),
                                    )
                                    .into_any_element()
                            } else {
                                Button::new("welcome-grok-signin", "Sign in with Grok")
                                    .full_width()
                                    .style(ButtonStyle::Outlined)
                                    .on_click(|_, _, cx| {
                                        let home = std::env::var("HOME")
                                            .or_else(|_| std::env::var("USERPROFILE"))
                                            .unwrap_or_default();
                                        let exe = if cfg!(target_os = "windows") {
                                            "grok.exe"
                                        } else {
                                            "grok"
                                        };
                                        let mut candidates = vec![std::path::PathBuf::from(&home)
                                            .join(".grok")
                                            .join("bin")
                                            .join(exe)];
                                        if !cfg!(target_os = "windows") {
                                            candidates
                                                .push(std::path::PathBuf::from("/opt/homebrew/bin/grok"));
                                            candidates
                                                .push(std::path::PathBuf::from("/usr/local/bin/grok"));
                                        }
                                        let mut launched = false;
                                        for bin in candidates.into_iter().filter(|p| p.exists()) {
                                            if std::process::Command::new(&bin)
                                                .args(["login", "--oauth"])
                                                .spawn()
                                                .is_ok()
                                            {
                                                launched = true;
                                                break;
                                            }
                                        }
                                        if !launched
                                            && std::process::Command::new(exe)
                                                .args(["login", "--oauth"])
                                                .spawn()
                                                .is_ok()
                                        {
                                            launched = true;
                                        }
                                        if !launched {
                                            cx.open_url("https://x.ai/cli");
                                        }
                                    })
                                    .into_any_element()
                            })
                    })
"""

with open(welcome_path, "r", encoding="utf-8") as f:
    welcome = f.read()

if "welcome-grok-signin" in welcome:
    print("welcome sign-in already patched")
elif WELCOME_ANCHOR in welcome:
    welcome = welcome.replace(WELCOME_ANCHOR, WELCOME_INSERT + WELCOME_ANCHOR, 1)
    with open(welcome_path, "w", encoding="utf-8") as f:
        f.write(welcome)
    print("welcome sign-in patched: Grok status plus sign-in button on the welcome page")
else:
    print("warning: welcome.rs anchor not found, sign-in button skipped", file=sys.stderr)
