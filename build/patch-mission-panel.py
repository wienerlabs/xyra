import os
import sys

SRC = sys.argv[1]
CRATE = f"{SRC}/crates/xyra_mission_ui"

CARGO = """[package]
name = "xyra_mission_ui"
version = "0.1.0"
edition.workspace = true
publish.workspace = true
license = "GPL-3.0-or-later"

[lints]
workspace = true

[lib]
path = "src/xyra_mission_ui.rs"

[dependencies]
anyhow.workspace = true
gpui.workspace = true
serde.workspace = true
serde_json.workspace = true
ui.workspace = true
workspace.workspace = true
zed_actions.workspace = true
"""

LIB = r'''use gpui::{
    Action, App, Context, Entity, EventEmitter, FocusHandle, Focusable, IntoElement,
    ParentElement,
    Pixels, Render, Styled, Task, Window, actions, px,
};
use serde::Deserialize;
use std::path::PathBuf;
use std::time::Duration;
use ui::{Tooltip, prelude::*};
use workspace::dock::{DockPosition, Panel, PanelEvent};
use workspace::Workspace;

actions!(xyra, [ToggleMissionPanel]);

#[derive(Clone, Deserialize, Default)]
struct MissionTicket {
    id: String,
    title: String,
    status: String,
    #[serde(default)]
    attempts: u32,
    #[serde(default)]
    commit: Option<String>,
}

#[derive(Clone, Deserialize, Default)]
struct MissionState {
    #[serde(default)]
    id: String,
    #[serde(default)]
    objective: String,
    #[serde(default)]
    status: String,
    #[serde(default)]
    sessions: u32,
    #[serde(default)]
    current: Option<String>,
    #[serde(default)]
    halt_reason: Option<String>,
    #[serde(default)]
    tickets: Vec<MissionTicket>,
}

impl MissionState {
    fn counted(&self) -> (usize, usize) {
        let total = self
            .tickets
            .iter()
            .filter(|t| t.status != "split")
            .count();
        let done = self.tickets.iter().filter(|t| t.status == "done").count();
        (done, total)
    }
}

pub struct MissionPanel {
    focus_handle: FocusHandle,
    state: Option<MissionState>,
    root: Option<PathBuf>,
    _poll: Task<()>,
}

impl MissionPanel {
    pub fn new(workspace: &Workspace, window: &mut Window, cx: &mut Context<Self>) -> Self {
        let root = workspace
            .visible_worktrees(cx)
            .next()
            .map(|tree| tree.read(cx).abs_path().to_path_buf());
        let poll = cx.spawn_in(window, async move |this, cx| {
            loop {
                cx.background_executor()
                    .timer(Duration::from_secs(2))
                    .await;
                if this.update(cx, |this, cx| {
                    this.reload();
                    cx.notify();
                }).is_err() {
                    break;
                }
            }
        });
        let mut panel = Self {
            focus_handle: cx.focus_handle(),
            state: None,
            root,
            _poll: poll,
        };
        panel.reload();
        panel
    }

    fn reload(&mut self) {
        let Some(root) = self.root.clone() else {
            return;
        };
        let path = root.join(".xyra").join("mission.json");
        self.state = std::fs::read_to_string(path)
            .ok()
            .and_then(|text| serde_json::from_str::<MissionState>(&text).ok());
    }

    fn run_cli(&self, args: Vec<String>) {
        let Some(root) = self.root.clone() else {
            return;
        };
        for base in ["/opt/homebrew/bin", "/usr/local/bin"] {
            let bin = PathBuf::from(base).join("xyra-mission");
            if bin.exists() {
                let _ = std::process::Command::new(bin)
                    .args(&args)
                    .arg("--path")
                    .arg(&root)
                    .spawn();
                return;
            }
        }
        let _ = std::process::Command::new("xyra-mission")
            .args(&args)
            .arg("--path")
            .arg(&root)
            .spawn();
    }

    fn status_color(status: &str) -> Color {
        match status {
            "done" => Color::Success,
            "running" => Color::Accent,
            "quarantined" => Color::Error,
            "retry" => Color::Warning,
            "split" => Color::Muted,
            _ => Color::Default,
        }
    }

    fn render_empty(&self) -> AnyElement {
        v_flex()
            .p_4()
            .gap_2()
            .child(Label::new("No mission in this project").size(LabelSize::Small))
            .child(
                Label::new(
                    "Start one from the terminal:\nxyra-mission start \"your objective\"",
                )
                .size(LabelSize::XSmall)
                .color(Color::Muted),
            )
            .into_any_element()
    }
}

impl Render for MissionPanel {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let Some(state) = self.state.clone() else {
            return v_flex()
                .size_full()
                .bg(cx.theme().colors().panel_background)
                .child(self.render_empty());
        };
        let (done, total) = state.counted();
        let percent = if total > 0 { done * 100 / total } else { 0 };
        let running = state.status == "running";

        let header = v_flex()
            .p_3()
            .gap_1()
            .border_b_1()
            .border_color(cx.theme().colors().border)
            .child(
                h_flex()
                    .justify_between()
                    .child(Label::new("Mission").size(LabelSize::Default))
                    .child(
                        Label::new(state.status.clone())
                            .size(LabelSize::XSmall)
                            .color(if running { Color::Accent } else { Color::Muted }),
                    ),
            )
            .child(
                Label::new(state.objective.clone())
                    .size(LabelSize::XSmall)
                    .color(Color::Muted),
            )
            .child(
                h_flex()
                    .gap_2()
                    .child(
                        div()
                            .h(px(6.))
                            .flex_1()
                            .rounded_sm()
                            .bg(cx.theme().colors().element_background)
                            .child(
                                div()
                                    .h_full()
                                    .w(relative(percent as f32 / 100.0))
                                    .rounded_sm()
                                    .bg(cx.theme().status().created),
                            ),
                    )
                    .child(
                        Label::new(format!("{done}/{total}"))
                            .size(LabelSize::XSmall)
                            .color(Color::Muted),
                    ),
            )
            .child(
                Label::new(format!(
                    "{} sessions{}",
                    state.sessions,
                    state
                        .halt_reason
                        .clone()
                        .map(|r| format!(", halted: {r}"))
                        .unwrap_or_default()
                ))
                .size(LabelSize::XSmall)
                .color(Color::Muted),
            );

        let controls = h_flex()
            .p_2()
            .gap_2()
            .border_b_1()
            .border_color(cx.theme().colors().border)
            .child(
                Button::new("mission-resume", "Resume")
                    .start_icon(Icon::new(IconName::PlayFilled).size(IconSize::Small))
                    .label_size(LabelSize::Small)
                    .size(ButtonSize::Compact)
                    .tooltip(Tooltip::text("Continue the mission until it is done"))
                    .on_click(cx.listener(|this, _, _, _| {
                        this.run_cli(vec!["daemon".to_string()]);
                    })),
            )
            .child(
                Button::new("mission-stop", "Stop")
                    .start_icon(Icon::new(IconName::Stop).size(IconSize::Small))
                    .label_size(LabelSize::Small)
                    .size(ButtonSize::Compact)
                    .tooltip(Tooltip::text("Halt after the current ticket"))
                    .on_click(cx.listener(|this, _, _, _| {
                        this.run_cli(vec!["stop".to_string()]);
                    })),
            );

        let tickets = v_flex().p_1().children(state.tickets.iter().map(|t| {
            let is_current = state.current.as_deref() == Some(t.id.as_str());
            h_flex()
                .w_full()
                .px_2()
                .py_1()
                .gap_2()
                .when(is_current, |this| {
                    this.bg(cx.theme().colors().element_selected).rounded_sm()
                })
                .child(
                    Label::new(t.id.clone())
                        .size(LabelSize::XSmall)
                        .color(Color::Muted),
                )
                .child(
                    div().flex_1().child(
                        Label::new(t.title.clone())
                            .size(LabelSize::Small)
                            .color(Self::status_color(&t.status)),
                    ),
                )
                .child(
                    Label::new(if t.status == "done" {
                        t.commit.clone().unwrap_or_default().chars().take(7).collect::<String>()
                    } else if t.attempts > 0 {
                        format!("{} try", t.attempts)
                    } else {
                        t.status.clone()
                    })
                    .size(LabelSize::XSmall)
                    .color(Color::Muted),
                )
        }));

        v_flex()
            .size_full()
            .bg(cx.theme().colors().panel_background)
            .child(header)
            .child(controls)
            .child(div().id("mission-tickets").flex_1().overflow_y_scroll().child(tickets))
    }
}

impl EventEmitter<PanelEvent> for MissionPanel {}

impl Focusable for MissionPanel {
    fn focus_handle(&self, _cx: &App) -> FocusHandle {
        self.focus_handle.clone()
    }
}

impl Panel for MissionPanel {
    fn persistent_name() -> &'static str {
        "XyraMissionPanel"
    }

    fn panel_key() -> &'static str {
        "XyraMissionPanel"
    }

    fn position(&self, _window: &Window, _cx: &App) -> DockPosition {
        DockPosition::Right
    }

    fn position_is_valid(&self, position: DockPosition) -> bool {
        matches!(position, DockPosition::Left | DockPosition::Right)
    }

    fn set_position(&mut self, _position: DockPosition, _window: &mut Window, _cx: &mut Context<Self>) {}

    fn default_size(&self, _window: &Window, _cx: &App) -> Pixels {
        px(360.)
    }

    fn icon(&self, _window: &Window, _cx: &App) -> Option<IconName> {
        Some(IconName::ListTree)
    }

    fn icon_tooltip(&self, _window: &Window, _cx: &App) -> Option<&'static str> {
        Some("Mission Panel")
    }

    fn toggle_action(&self) -> Box<dyn Action> {
        Box::new(ToggleMissionPanel)
    }

    fn activation_priority(&self) -> u32 {
        7
    }
}

impl MissionPanel {
    pub fn load(
        workspace: gpui::WeakEntity<Workspace>,
        mut cx: gpui::AsyncWindowContext,
    ) -> Task<anyhow::Result<Entity<Self>>> {
        cx.spawn(async move |cx| {
            workspace.update_in(cx, |workspace, window, cx| {
                cx.new(|cx| MissionPanel::new(workspace, window, cx))
            })
        })
    }
}

pub fn init(cx: &mut App) {
    cx.observe_new(|workspace: &mut Workspace, _window, _cx| {
        workspace.register_action(|workspace, _: &ToggleMissionPanel, window, cx| {
            workspace.toggle_panel_focus::<MissionPanel>(window, cx);
        });
    })
    .detach();
}
'''

os.makedirs(f"{CRATE}/src", exist_ok=True)
with open(f"{CRATE}/Cargo.toml", "w", encoding="utf-8") as f:
    f.write(CARGO)
with open(f"{CRATE}/src/xyra_mission_ui.rs", "w", encoding="utf-8") as f:
    f.write(LIB)

root_cargo = f"{SRC}/Cargo.toml"
with open(root_cargo, "r", encoding="utf-8") as f:
    cargo = f.read()

if "xyra_mission_ui" not in cargo:
    cargo = cargo.replace('    "crates/workspace",', '    "crates/workspace",\n    "crates/xyra_mission_ui",', 1)
    cargo = cargo.replace('workspace = { path = "crates/workspace" }',
                          'workspace = { path = "crates/workspace" }\nxyra_mission_ui = { path = "crates/xyra_mission_ui" }', 1)
    with open(root_cargo, "w", encoding="utf-8") as f:
        f.write(cargo)
    print("mission panel crate registered in the workspace")
else:
    print("mission panel crate already registered")

zed_cargo = f"{SRC}/crates/zed/Cargo.toml"
with open(zed_cargo, "r", encoding="utf-8") as f:
    zc = f.read()
if "xyra_mission_ui" not in zc:
    zc = zc.replace("workspace.workspace = true",
                    "workspace.workspace = true\nxyra_mission_ui.workspace = true", 1)
    with open(zed_cargo, "w", encoding="utf-8") as f:
        f.write(zc)
    print("mission panel wired into the zed crate")

zed_rs = f"{SRC}/crates/zed/src/zed.rs"
with open(zed_rs, "r", encoding="utf-8") as f:
    zed_src = f.read()
if "MissionPanel" not in zed_src:
    anchor = "        let debug_panel = DebugPanel::load(workspace_handle.clone(), cx);"
    add = "            add_panel_when_ready(debug_panel, workspace_handle.clone(), cx.clone()),"
    if anchor in zed_src and add in zed_src:
        zed_src = zed_src.replace(
            anchor,
            anchor + "\n        let mission_panel = xyra_mission_ui::MissionPanel::load("
                     "workspace_handle.clone(), cx.clone());", 1)
        zed_src = zed_src.replace(
            add,
            add + "\n            add_panel_when_ready(mission_panel, workspace_handle.clone(), cx.clone()),", 1)
        with open(zed_rs, "w", encoding="utf-8") as f:
            f.write(zed_src)
        print("mission panel added to the workspace panel set")
    else:
        print("warning: panel registration anchors not found", file=sys.stderr)

main_rs = f"{SRC}/crates/zed/src/main.rs"
with open(main_rs, "r", encoding="utf-8") as f:
    main = f.read()
if "xyra_mission_ui::init" not in main:
    anchor = "    let app_state = Arc::new(AppState {"
    if anchor in main:
        main = main.replace(anchor, "    xyra_mission_ui::init(cx);\n" + anchor, 1)
        with open(main_rs, "w", encoding="utf-8") as f:
            f.write(main)
        print("mission panel init call inserted")
    else:
        print("warning: could not find the init anchor in main.rs", file=sys.stderr)
