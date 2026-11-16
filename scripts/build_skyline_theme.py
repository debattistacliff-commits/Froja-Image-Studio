"""Generate app/skyline-theme.generated.css.

Reads Froja's existing stylesheets and writes a "Skyline" (porcelain / brushed-silver / red-LED)
version of every colour, scoped to `.studio.theme-skyline`. Re-run after changing any tool CSS:

    python scripts/build_skyline_theme.py            (light Skyline)
    python scripts/build_skyline_theme.py graphite   (dark Graphite LED)
"""
import colorsys
import re
from pathlib import Path

import tinycss2

APP = Path(__file__).resolve().parent.parent / "app"
SOURCES = ["globals.css", "library.css", "froja-enhancements.css", "professional.css",
           "sketch-3d-studio.css", "reference-composer-studio.css", "sensenova-studio.css",
           "variation-lab.css", "prompt-batch-studio.css", "portrait-transformer.css",
           "portrait-transformer-fixes.css"]
import sys

MODE = sys.argv[1] if len(sys.argv) > 1 else "skyline"  # "skyline" (light) or "graphite" (dark)
OUT = APP / f"{MODE}-theme.generated.css"
SCOPE = f".studio.theme-{MODE}"
OTHER_THEMES = re.compile(r"\.theme-(forge|midnight|bronze|contrast|stainless|cyan-metal|original)\b")

LED_RED = (206, 44, 34)
LED_GREEN = (36, 150, 76)
LED_AMBER = (196, 122, 12)
SHADOW = (40, 42, 48)

NAMED = {"white": (255, 255, 255, 1.0), "black": (0, 0, 0, 1.0)}
COLOR_RE = re.compile(
    r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{4}\b|#[0-9a-fA-F]{3}\b"
    r"|rgba?\([^)]*\)|\b(?:white|black)\b")


def parse(tok):
    t = tok.lower()
    if t in NAMED:
        return NAMED[t]
    if t.startswith("#"):
        h = t[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return r, g, b, a
    nums = re.findall(r"[-\d.]+%?", t[t.index("(") + 1:-1])
    if len(nums) < 3:
        return None
    vals = []
    for i, n in enumerate(nums[:4]):
        if n.endswith("%"):
            v = float(n[:-1]) / 100 * (255 if i < 3 else 1)
        else:
            v = float(n)
        vals.append(v)
    if len(vals) == 3:
        vals.append(1.0)
    return vals[0], vals[1], vals[2], vals[3]


def led(a):
    """The switchable LED accent (red or ice blue), set by .led-* classes in skyline-theme.css."""
    if a >= 0.999:
        return "var(--sk-accent-ink)"
    return f"color-mix(in srgb, var(--sk-accent-ink) {round(a * 100)}%, transparent)"


def fmt(rgb, a):
    if rgb is LED_RED:
        return led(a)
    r, g, b = (max(0, min(255, round(c))) for c in rgb)
    if a >= 0.999:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r},{g},{b},{round(a, 3)})"


def hls(r, g, b):
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)


def from_hls(h, l, s):
    return tuple(c * 255 for c in colorsys.hls_to_rgb(h, max(0, min(1, l)), max(0, min(1, s))))


def accent_led(h):
    deg = h * 360
    if 75 <= deg < 150:
        return LED_GREEN
    if 25 <= deg < 75:
        return LED_AMBER
    return LED_RED  # teal, cyan, blue, violet and red all become the red LED


def remap_dark(color, role):
    """Graphite LED theme: neutral brushed-graphite surfaces, light ink, LED accents."""
    r, g, b, a = color
    h, l, s = hls(r, g, b)
    accent = s > 0.35 and 0.18 < l < 0.88 and max(r, g, b) - min(r, g, b) > 40
    if role == "surface":
        if accent:
            return fmt(from_hls(0.6, 0.20, 0.04), a)
        if a < 0.999 and l < 0.2:  # dark overlays / backdrops stay dark, slightly deeper
            return fmt((4, 5, 7), min(1, a + 0.04))
        nl = 0.07 + l * 0.32 if l < 0.5 else 0.23 + (l - 0.5) * 0.2
        return fmt(from_hls(0.6, nl, 0.06), a)
    if role == "ink":
        if accent:
            led_rgb = accent_led(h)
            return led(a) if led_rgb is LED_RED else fmt(tuple(min(255, c * 1.45) for c in led_rgb), a)
        if l > 0.45:
            return fmt(from_hls(0.6, max(l, 0.62), 0.05), a)
        return fmt(from_hls(0.6, 0.86 - l * 0.4, 0.05), a)
    if role == "line":
        if accent:
            return led(min(a, 0.55))
        return fmt(from_hls(0.6, 0.15 + l * 0.18, 0.05), a)
    if role == "shadow":
        if accent:
            return led(min(a, 0.45))
        if l < 0.35:
            return fmt((0, 0, 0), min(1, a * 1.1))
        return fmt((255, 255, 255), a * 0.35)
    return None


def remap(color, role):
    if MODE == "graphite":
        return remap_dark(color, role)
    r, g, b, a = color
    h, l, s = hls(r, g, b)
    accent = s > 0.35 and 0.18 < l < 0.88 and max(r, g, b) - min(r, g, b) > 40
    if role == "surface":
        if accent:
            return fmt(from_hls(0.12, 0.86, 0.05), a)
        nl = 0.965 - l * 0.25 if l < 0.5 else 0.84 + (l - 0.5) * 0.26
        if a < 0.999 and l < 0.2:  # dark overlays / backdrops -> frosted porcelain
            return fmt(from_hls(0.12, 0.93, 0.08), min(1, a + 0.05))
        return fmt(from_hls(0.12, nl, 0.07), a)
    if role == "ink":
        if accent:
            return fmt(accent_led(h), a)
        if l > 0.45:
            return fmt(from_hls(0.6, 0.14 + (1 - l) * 0.55, 0.05), a)
        return fmt(from_hls(0.6, min(l, 0.2), 0.05), a)
    if role == "line":
        if accent:
            return fmt(from_hls(0.58, 0.74, 0.05), min(a, 0.9))
        return fmt(from_hls(0.58, 0.80 - l * 0.12, 0.04), a)
    if role == "shadow":
        if accent:
            return fmt(LED_RED, min(a, 0.35))
        if l < 0.35:
            return fmt(SHADOW, a * 0.45)
        return fmt((255, 255, 255), a)
    return None


def role_for(prop, value):
    p = prop.lower()
    if p.startswith("--"):
        if re.search(r"bg|panel|surface|card|back", p):
            return "surface"
        if re.search(r"line|border|stroke", p):
            return "line"
        if re.search(r"muted|text|ink|fg|teal|accent", p):
            return "ink"
        return "auto"
    if p in ("background", "background-color", "background-image"):
        return "surface"
    if p in ("color", "fill", "stroke", "caret-color", "-webkit-text-fill-color", "accent-color",
             "text-decoration-color"):
        return "ink"
    if p.startswith("border") or p.startswith("outline") or p == "column-rule":
        return "line"
    if p in ("box-shadow", "text-shadow", "filter"):
        return "shadow"
    return None


def convert_value(prop, value):
    role = role_for(prop, value)
    if not role:
        return None
    changed = False

    def sub(m):
        nonlocal changed
        c = parse(m.group(0))
        if c is None:
            return m.group(0)
        use = role
        if role == "auto":
            use = "surface" if hls(*c[:3])[1] < 0.5 else "ink"
        new = remap(c, use)
        if new is None:
            return m.group(0)
        changed = True
        return new

    out = COLOR_RE.sub(sub, value)
    return out if changed else None


def scope_selector(sel):
    sel = sel.strip()
    if not sel or OTHER_THEMES.search(sel):
        return None
    if sel in (":root", "html", "body", "#root", "html body"):
        return SCOPE
    if sel.startswith(".studio"):
        return SCOPE + sel[len(".studio"):]
    if sel.startswith(("html ", "body ", ":root ")):
        sel = sel.split(" ", 1)[1]
    return f"{SCOPE} {sel}"


def split_selectors(prelude):
    parts, depth, cur = [], 0, ""
    for ch in prelude:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def convert_rules(rules):
    out = []
    for rule in rules:
        if rule.type == "qualified-rule":
            prelude = tinycss2.serialize(rule.prelude).strip()
            sels = [s for s in (scope_selector(x) for x in split_selectors(prelude)) if s]
            if not sels:
                continue
            decls = []
            for d in tinycss2.parse_blocks_contents(rule.content, skip_whitespace=True, skip_comments=True):
                if d.type != "declaration":
                    continue
                new = convert_value(d.name, tinycss2.serialize(d.value).strip())
                if new:
                    decls.append(f"{d.name}:{new} !important")
            if decls:
                out.append(",".join(sels) + "{" + ";".join(decls) + "}")
        elif rule.type == "at-rule" and rule.lower_at_keyword in ("media", "supports") and rule.content:
            inner = convert_rules(tinycss2.parse_rule_list(rule.content, skip_whitespace=True, skip_comments=True))
            if inner:
                out.append(f"@{rule.at_keyword} {tinycss2.serialize(rule.prelude).strip()}{{" + "\n".join(inner) + "}")
    return out


def main():
    chunks = [f"/* AUTO-GENERATED by scripts/build_skyline_theme.py - do not edit by hand. */"]
    total = 0
    for name in SOURCES:
        path = APP / name
        if not path.exists():
            continue
        rules = tinycss2.parse_stylesheet(path.read_text(encoding="utf-8"), skip_whitespace=True, skip_comments=True)
        converted = convert_rules(rules)
        total += len(converted)
        chunks.append(f"/* from {name}: {len(converted)} rules */")
        chunks.extend(converted)
    OUT.write_text("\n".join(chunks) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.name}: {total} rules")


if __name__ == "__main__":
    main()
