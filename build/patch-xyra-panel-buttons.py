import sys

SRC = sys.argv[1]
path = f"{SRC}/crates/workspace/src/status_bar.rs"

ANCHOR = """            .children(self.left_items.iter().enumerate().map(|(index, item)| {
                render_hideable_item("status-bar-left", index, item.as_ref(), cx)
            }))
    }"""

INSERT = """            .children(self.left_items.iter().enumerate().map(|(index, item)| {
                render_hideable_item("status-bar-left", index, item.as_ref(), cx)
            }))
            .child(Self::render_xyra_views())
    }

    fn render_xyra_views() -> impl IntoElement {
        let views: [(&'static str, &'static str, &'static str, IconName); 4] = [
            ("xyra-view-agents", "Agents", "hud", IconName::ZedAssistant),
            ("xyra-view-fleet", "Fleet", "fleet", IconName::GitBranch),
            ("xyra-view-map", "Map", "topology", IconName::ListTree),
            ("xyra-view-guard", "Guard", "secops", IconName::Lock),
        ];
        h_flex()
            .gap_1()
            .children(views.map(|(id, label, view, icon)| {
                Button::new(id, label)
                    .start_icon(Icon::new(icon).size(IconSize::Small))
                    .label_size(LabelSize::Small)
                    .size(ButtonSize::Compact)
                    .tooltip(Tooltip::text(match view {
                        "hud" => "Live agent orchestration",
                        "fleet" => "Connect and inspect fleet repositories",
                        "topology" => "Project topology map",
                        _ => "Security and cost flags",
                    }))
                    .on_click(move |_, _, cx| {
                        let root = std::env::current_dir()
                            .map(|p| p.to_string_lossy().to_string())
                            .unwrap_or_default();
                        let (program, args): (&str, Vec<String>) = if view == "fleet" {
                            ("xyra-fleet", vec!["list".to_string()])
                        } else {
                            ("xyra-views", vec![view.to_string(), root])
                        };
                        let mut candidates = vec![
                            std::path::PathBuf::from("/opt/homebrew/bin").join(program),
                            std::path::PathBuf::from("/usr/local/bin").join(program),
                        ];
                        if let Ok(home) = std::env::var("HOME") {
                            candidates.push(std::path::PathBuf::from(home).join(".local/bin").join(program));
                        }
                        let mut launched = false;
                        for bin in candidates.into_iter().filter(|p| p.exists()) {
                            if std::process::Command::new(&bin).args(&args).spawn().is_ok() {
                                launched = true;
                                break;
                            }
                        }
                        if !launched && std::process::Command::new(program).args(&args).spawn().is_err() {
                            cx.open_url("https://github.com/wienerlabs/xyra#the-autonomy-engine");
                        }
                    })
            }))
    }"""

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

if "render_xyra_views" in content:
    print("xyra view buttons already patched")
elif ANCHOR in content:
    content = content.replace(ANCHOR, INSERT, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("xyra view buttons patched: Agents, Fleet, Map, Guard in the status bar")
else:
    print("warning: status_bar.rs anchor not found, view buttons skipped", file=sys.stderr)
