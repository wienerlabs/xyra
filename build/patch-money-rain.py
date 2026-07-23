import sys

SRC = sys.argv[1]

MODULE_PATH = f"{SRC}/crates/agent_ui/src/money_rain.rs"
MODULE_SOURCE = '''use gpui::{Animation, AnimationExt, AnyElement, px, relative};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use ui::prelude::*;

static STARTED_AT_MS: AtomicU64 = AtomicU64::new(0);
const RAIN_DURATION_MS: u64 = 3000;
const BILL_COUNT: usize = 22;

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|elapsed| elapsed.as_millis() as u64)
        .unwrap_or(0)
}

pub(crate) fn start() {
    STARTED_AT_MS.store(now_ms(), Ordering::Relaxed);
}

pub(crate) fn is_active() -> bool {
    let started = STARTED_AT_MS.load(Ordering::Relaxed);
    started != 0 && now_ms().saturating_sub(started) < RAIN_DURATION_MS
}

pub(crate) fn overlay() -> Option<AnyElement> {
    if !is_active() {
        return None;
    }
    let bills = ["\\u{1f4b8}", "\\u{1f4b5}", "\\u{1f911}", "\\u{1f4b0}"];
    Some(
        div()
            .absolute()
            .inset_0()
            .overflow_hidden()
            .children((0..BILL_COUNT).map(|ix| {
                let column = ((ix * 47) % 100) as f32 / 100.0;
                let start_top = -80.0 - ((ix * 53) % 420) as f32;
                let fall_ms = 1400 + ((ix * 137) % 900) as u64;
                let bill = bills[ix % bills.len()];
                div()
                    .absolute()
                    .left(relative(column))
                    .top(px(start_top))
                    .text_size(px(46.))
                    .child(bill)
                    .with_animation(
                        ("xyra-money-rain", ix),
                        Animation::new(Duration::from_millis(fall_ms))
                            .with_easing(|t| t * t),
                        move |element, delta| element.top(px(start_top + delta * 1700.0)),
                    )
            }))
            .into_any_element(),
    )
}
'''

MOD_ANCHOR = "mod mode_selector;"
MOD_INSERT = "mod mode_selector;\nmod money_rain;"

TRIGGER_ANCHOR = """                if !sent_queued_message {
                    let used_tools = thread.read(cx).used_tools_since_last_user_message();
                    self.notify_with_sound(
                        if used_tools {
                            "Finished running tools"
                        } else {
                            "New message"
                        },
                        IconName::ZedAssistant,
                        window,
                        cx,
                    );
                }"""
TRIGGER_REPLACEMENT = """                if !sent_queued_message {
                    let used_tools = thread.read(cx).used_tools_since_last_user_message();
                    self.notify_with_sound(
                        if used_tools {
                            "Finished running tools"
                        } else {
                            "New message"
                        },
                        IconName::ZedAssistant,
                        window,
                        cx,
                    );
                    crate::money_rain::start();
                    cx.notify();
                    cx.spawn(async move |this, cx| {
                        cx.background_executor()
                            .timer(std::time::Duration::from_millis(3200))
                            .await;
                        this.update(cx, |_, cx| cx.notify()).ok();
                    })
                    .detach();
                }"""

RENDER_ROOT_ANCHOR = """        v_flex()
            .track_focus(&self.focus_handle)
            .size_full()
            .bg(cx.theme().colors().panel_background)
            .child(v_flex().flex_1().min_h_0().child(content))"""
RENDER_ROOT_REPLACEMENT = """        v_flex()
            .track_focus(&self.focus_handle)
            .size_full()
            .relative()
            .bg(cx.theme().colors().panel_background)
            .child(v_flex().flex_1().min_h_0().child(content))"""

RENDER_TAIL_ANCHOR = """                        self.render_request_elicitations(connection, cx.entity().downgrade(), cx)
                    },
                ))
            })
    }
}"""
RENDER_TAIL_REPLACEMENT = """                        self.render_request_elicitations(connection, cx.entity().downgrade(), cx)
                    },
                ))
            })
            .children(crate::money_rain::overlay())
    }
}"""

with open(MODULE_PATH, "w", encoding="utf-8") as f:
    f.write(MODULE_SOURCE)
print("money rain module written")

lib_path = f"{SRC}/crates/agent_ui/src/agent_ui.rs"
with open(lib_path, "r", encoding="utf-8") as f:
    lib = f.read()
if "mod money_rain;" in lib:
    print("money rain module already registered")
elif MOD_ANCHOR in lib:
    lib = lib.replace(MOD_ANCHOR, MOD_INSERT, 1)
    with open(lib_path, "w", encoding="utf-8") as f:
        f.write(lib)
    print("money rain module registered")
else:
    print("warning: agent_ui.rs mod anchor not found", file=sys.stderr)

conv_path = f"{SRC}/crates/agent_ui/src/conversation_view.rs"
with open(conv_path, "r", encoding="utf-8") as f:
    conv = f.read()

changed = False
if "money_rain::start()" in conv:
    print("money rain trigger already patched")
elif TRIGGER_ANCHOR in conv:
    conv = conv.replace(TRIGGER_ANCHOR, TRIGGER_REPLACEMENT, 1)
    changed = True
    print("money rain trigger patched: fires when the agent finishes")
else:
    print("warning: conversation_view.rs trigger anchor not found", file=sys.stderr)

if "money_rain::overlay()" in conv:
    print("money rain overlay already patched")
else:
    if RENDER_ROOT_ANCHOR in conv:
        conv = conv.replace(RENDER_ROOT_ANCHOR, RENDER_ROOT_REPLACEMENT, 1)
        changed = True
    else:
        print("warning: conversation_view.rs render root anchor not found", file=sys.stderr)
    if RENDER_TAIL_ANCHOR in conv:
        conv = conv.replace(RENDER_TAIL_ANCHOR, RENDER_TAIL_REPLACEMENT, 1)
        changed = True
        print("money rain overlay patched: renders above the conversation")
    else:
        print("warning: conversation_view.rs render tail anchor not found", file=sys.stderr)

if changed:
    with open(conv_path, "w", encoding="utf-8") as f:
        f.write(conv)
