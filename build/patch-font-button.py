import sys

SRC = sys.argv[1]
path = f"{SRC}/crates/title_bar/src/title_bar.rs"

ANCHOR = """                .child(self.render_call_controls(window, cx))
                .children(self.render_connection_status(status, cx))
                .child(self.update_version.clone())"""

INSERT = """
                .child(
                    IconButton::new("xyra-decrease-font", IconName::FontSize)
                        .icon_size(IconSize::XSmall)
                        .tooltip(Tooltip::text("Decrease font size"))
                        .on_click(|_, window, cx| {
                            window.dispatch_action(
                                zed_actions::DecreaseBufferFontSize::default().boxed_clone(),
                                cx,
                            );
                        }),
                )
                .child(
                    IconButton::new("xyra-increase-font", IconName::FontSize)
                        .icon_size(IconSize::Small)
                        .tooltip(Tooltip::text("Increase font size"))
                        .on_click(|_, window, cx| {
                            window.dispatch_action(
                                zed_actions::IncreaseBufferFontSize::default().boxed_clone(),
                                cx,
                            );
                        }),
                )"""

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

if "xyra-increase-font" in content:
    print("font button patch already applied")
elif ANCHOR in content:
    content = content.replace(ANCHOR, ANCHOR + INSERT, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("font button patch applied: increase/decrease in the title bar")
else:
    print("warning: title_bar.rs not in the expected shape, font button skipped", file=sys.stderr)
