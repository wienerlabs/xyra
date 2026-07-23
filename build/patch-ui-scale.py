import sys

SRC = sys.argv[1]

button_path = f"{SRC}/crates/ui/src/components/button/button_like.rs"

HEIGHTS_OLD = """            ButtonSize::Large => rems_from_px(32.),
            ButtonSize::Medium => rems_from_px(28.),
            ButtonSize::Default => rems_from_px(22.),
            ButtonSize::Compact => rems_from_px(18.),
            ButtonSize::None => rems_from_px(16.),"""
HEIGHTS_NEW = """            ButtonSize::Large => rems_from_px(38.),
            ButtonSize::Medium => rems_from_px(33.),
            ButtonSize::Default => rems_from_px(27.),
            ButtonSize::Compact => rems_from_px(22.),
            ButtonSize::None => rems_from_px(18.),"""

PADDING_OLD = """                ButtonSize::Default | ButtonSize::Compact => {
                    this.px(DynamicSpacing::Base04.rems(cx))
                }"""
PADDING_NEW = """                ButtonSize::Default | ButtonSize::Compact => {
                    this.px(DynamicSpacing::Base06.rems(cx))
                }"""

with open(button_path, "r", encoding="utf-8") as f:
    content = f.read()

if HEIGHTS_NEW in content:
    print("button heights already patched")
elif HEIGHTS_OLD in content:
    content = content.replace(HEIGHTS_OLD, HEIGHTS_NEW, 1)
    if PADDING_OLD in content:
        content = content.replace(PADDING_OLD, PADDING_NEW, 1)
    with open(button_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("button sizes patched: all buttons taller with roomier padding")
else:
    print("warning: button_like.rs heights anchor not found, skipped", file=sys.stderr)

icon_path = f"{SRC}/crates/ui/src/components/icon.rs"

ICON_PAD_OLD = """            IconSize::XSmall => DynamicSpacing::Base02.px(cx),
            IconSize::Small => DynamicSpacing::Base02.px(cx),
            IconSize::Medium => DynamicSpacing::Base02.px(cx),"""
ICON_PAD_NEW = """            IconSize::XSmall => DynamicSpacing::Base03.px(cx),
            IconSize::Small => DynamicSpacing::Base03.px(cx),
            IconSize::Medium => DynamicSpacing::Base03.px(cx),"""

with open(icon_path, "r", encoding="utf-8") as f:
    icon = f.read()

if ICON_PAD_NEW in icon:
    print("icon button padding already patched")
elif ICON_PAD_OLD in icon:
    icon = icon.replace(ICON_PAD_OLD, ICON_PAD_NEW, 1)
    with open(icon_path, "w", encoding="utf-8") as f:
        f.write(icon)
    print("icon button padding patched: square icon buttons larger")
else:
    print("warning: icon.rs padding anchor not found, skipped", file=sys.stderr)
