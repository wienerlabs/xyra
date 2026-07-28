import sys

SRC = sys.argv[1]

dock_path = f"{SRC}/crates/workspace/src/dock.rs"
DOCK_ANCHOR = """                            let button = IconButton::new((name, is_active_button as u64), icon)
                                .icon_size(IconSize::Small)
                                .toggle_state(is_active_button)"""
DOCK_REPLACEMENT = """                            let label = icon_tooltip
                                .trim_end_matches(" Panel")
                                .trim_end_matches(" Dock");
                            let button = Button::new((name, is_active_button as u64), label)
                                .start_icon(Icon::new(icon).size(IconSize::Small))
                                .label_size(LabelSize::Small)
                                .size(ButtonSize::Compact)
                                .toggle_state(is_active_button)"""

with open(dock_path, "r", encoding="utf-8") as f:
    dock = f.read()
if "trim_end_matches(\" Panel\")" in dock:
    print("dock labels already patched")
elif DOCK_ANCHOR in dock:
    dock = dock.replace(DOCK_ANCHOR, DOCK_REPLACEMENT, 1)
    with open(dock_path, "w", encoding="utf-8") as f:
        f.write(dock)
    print("dock labels patched: every panel toggle now shows its name")
else:
    print("warning: dock.rs anchor not found, panel labels skipped", file=sys.stderr)

search_path = f"{SRC}/crates/search/src/search_status_button.rs"
SEARCH_ANCHOR = """            IconButton::new("project-search-indicator", SEARCH_ICON)
                .icon_size(IconSize::Small)
                .tooltip(move |_window, cx| {"""
SEARCH_REPLACEMENT = """            Button::new("project-search-indicator", "Search")
                .start_icon(Icon::new(SEARCH_ICON).size(IconSize::Small))
                .label_size(LabelSize::Small)
                .size(ButtonSize::Compact)
                .tooltip(move |_window, cx| {"""

with open(search_path, "r", encoding="utf-8") as f:
    search = f.read()
if 'Button::new("project-search-indicator", "Search")' in search:
    print("search label already patched")
elif SEARCH_ANCHOR in search:
    search = search.replace(SEARCH_ANCHOR, SEARCH_REPLACEMENT, 1)
    with open(search_path, "w", encoding="utf-8") as f:
        f.write(search)
    print("search label patched")
else:
    print("warning: search_status_button.rs anchor not found, skipped", file=sys.stderr)

agent_path = f"{SRC}/crates/agent_ui/src/agent_panel.rs"
AGENT_ANCHOR = """                .trigger_with_tooltip(
                    IconButton::new("new_thread_menu_btn", IconName::Plus)
                        .icon_size(IconSize::Small),"""
AGENT_REPLACEMENT = """                .trigger_with_tooltip(
                    Button::new("new_thread_menu_btn", "New")
                        .start_icon(Icon::new(IconName::Plus).size(IconSize::Small))
                        .label_size(LabelSize::Small),"""

with open(agent_path, "r", encoding="utf-8") as f:
    agent = f.read()
if 'Button::new("new_thread_menu_btn", "New")' in agent:
    print("agent new button label already patched")
elif AGENT_ANCHOR in agent:
    agent = agent.replace(AGENT_ANCHOR, AGENT_REPLACEMENT, 1)
    with open(agent_path, "w", encoding="utf-8") as f:
        f.write(agent)
    print("agent new button label patched")
else:
    print("warning: agent_panel.rs new button anchor not found, skipped", file=sys.stderr)
