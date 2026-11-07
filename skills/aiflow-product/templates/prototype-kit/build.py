# -*- coding: utf-8 -*-
"""aiflow 原型图构建：把 _src/ 下页面里的 kit.css 引用替换成内联样式，输出到本目录。
拼好的完整样式另存为 _built.css，做「样式包和组件库对照」时给 scripts/parity/kit.html 用（?css=地址）。
样式按顺序拼接：_src/kit.css → 样式预设 _src/presets/<名>.css（design-system.md 写了「样式预设」时）
→ ../design-system.md 令牌表的覆盖 → _src/theme.css（如果有）。后面的覆盖前面的。
生成的页面不依赖任何外部文件，任何查看器打开都一样。以 _ 开头的文件（如 _template.html）不输出。
用法：把整个 prototype-kit 目录复制为 <项目>/.aiflow/prototype/，在 _src/ 下照 _template.html 写页面，运行 python build.py"""
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "_src"
PRESETS = SRC / "presets"
SPEC = HERE.parent / "design-system.md"
TAG = '<link rel="stylesheet" href="kit.css">'
BASES = ("primary", "success", "warning", "error", "info")
DEFAULT_WEIGHTS = {"bg": 0.9, "bd": 0.55, "text": 0.2}
# 中文 Windows 上被管道调用时输出默认是 GBK，读输出的 AI 看到的是乱码；和 check.py 一样改用 UTF-8。
for stream in (sys.stdout, sys.stderr):
    try:
        if os.environ.get("PYTHONIOENCODING"):
            stream.reconfigure(errors="replace")
        else:
            stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def read_tokens(text):
    """读 design-system.md 里第一张带「变量」「取值」列的表；取值为「按默认」的跳过。"""
    tokens, header = {}, None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            if header:
                break
            continue
        cells = [c.strip().strip("`").strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            if "变量" in cells and "取值" in cells:
                header = cells
            continue
        if all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells):
            continue
        data = dict(zip(header, cells))
        name, value = data.get("变量", ""), data.get("取值", "")
        if not re.fullmatch(r"--[a-z0-9-]+", name) or not value or value.startswith("按默认"):
            continue
        if re.search(r"[;{}<>]", value):
            sys.exit("design-system.md 里 %s 的取值含有非法字符：%s" % (name, value))
        tokens[name] = value
    return tokens


def read_preset(text):
    """读「样式预设：xxx」，取开头的预设名；没写、写「无」或还是模板占位时返回 None。"""
    match = re.search(r"^\s*-\s*样式预设\s*[:：]\s*(.*?)\s*$", text, re.M)
    if not match:
        return None
    value = match.group(1).strip("`").strip()
    if not value or value.startswith("<") or value.startswith("无"):
        return None
    name = re.match(r"[A-Za-z0-9_-]+", value)
    return name.group(0) if name else value


def mix(hex_color, other, weight):
    """把颜色按 weight 混向 other（白或黑），返回 #rrggbb；不是 #rrggbb 时返回 None。"""
    match = re.fullmatch(r"#([0-9a-fA-F]{6})", hex_color)
    if not match:
        return None
    rgb = [int(match.group(1)[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(round(c + (o - c) * weight) for c, o in zip(rgb, other))


def derive(tokens, weights):
    """改了主色、成功、警告、错误、信息色时，派生浅色背景、描边、文字色；令牌表里写了的不覆盖。"""
    result = dict(tokens)
    for base in BASES:
        value = tokens.get("--" + base)
        if not value:
            continue
        derived = {"bg": mix(value, (255, 255, 255), weights["bg"]), "bd": mix(value, (255, 255, 255), weights["bd"]),
                   "text": mix(value, (0, 0, 0), weights["text"])}
        if derived["bg"] is None:
            print("提示：%s 不是 #rrggbb 格式，浅色背景、描边、文字色没有派生" % ("--" + base))
            continue
        for suffix, color in derived.items():
            result.setdefault("--%s-%s" % (base, suffix), color)
    return result


css = (SRC / "kit.css").read_text(encoding="utf-8")
weights = dict(DEFAULT_WEIGHTS)
spec_text = SPEC.read_text(encoding="utf-8") if SPEC.exists() else ""
preset = read_preset(spec_text)
if preset:
    path = PRESETS / ("%s.css" % preset)
    if not path.exists():
        names = "、".join(sorted(p.stem for p in PRESETS.glob("*.css"))) or "无"
        sys.exit("design-system.md 写的样式预设「%s」不存在；可用的预设：%s" % (preset, names))
    preset_css = path.read_text(encoding="utf-8")
    directive = re.search(r"derive:\s*bg=([\d.]+)\s+bd=([\d.]+)\s+text=([\d.]+)", preset_css)
    if directive:
        weights = {"bg": float(directive.group(1)), "bd": float(directive.group(2)), "text": float(directive.group(3))}
    css += "\n/* 来自样式预设 %s */\n" % preset + preset_css
    print("用了样式预设：%s" % preset)
if SPEC.exists():
    tokens = derive(read_tokens(spec_text), weights)
    known = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
    for name in sorted(set(tokens) - known):
        print("提示：样式包里没有变量 %s，这个令牌不会生效" % name)
    tokens = {name: value for name, value in tokens.items() if name in known}
    if tokens:
        css += "\n/* 来自 .aiflow/design-system.md 的设计令牌 */\n:root { %s }\n" % " ".join("%s:%s;" % item for item in tokens.items())
        print("设计规范覆盖了 %d 个令牌：%s" % (len(tokens), "、".join(sorted(tokens))))
    else:
        print("设计规范的令牌全部按默认")
else:
    print("提示：没有 %s，按样式包默认（Ant Design 默认主题）构建" % SPEC)
theme = SRC / "theme.css"
if theme.exists():
    css += "\n/* 来自 _src/theme.css */\n" + theme.read_text(encoding="utf-8")
    print("追加了 _src/theme.css")

(HERE / "_built.css").write_text(css, encoding="utf-8", newline="\n")
for page in sorted(SRC.glob("*.html")):
    if page.name.startswith("_"):
        continue
    text = page.read_text(encoding="utf-8")
    assert text.count(TAG) == 1, "%s 必须恰好引用一次 kit.css" % page.name
    inline = re.findall(r'style="[^"]*(?:#[0-9a-fA-F]{3,8}\b|rgba?\()', text)
    if inline:
        print("提示：%s 有 %d 处行内样式写死了颜色，换设计规范时不会跟着变；改用 kit.css 的变量或类" % (page.name, len(inline)))
    sizes = re.findall(r'style="[^"]*font-size:\s*\d', text)
    if sizes:
        print("提示：%s 有 %d 处行内样式改了字号，前端用组件库默认值时会和设计稿对不上；改用 kit.css 的类，确实要改就写进 03-design.md「实现时要改组件库默认值的地方」" % (page.name, len(sizes)))
    (HERE / page.name).write_text(text.replace(TAG, "<style>\n" + css + "</style>"), encoding="utf-8", newline="\n")
    print("built", page.name)
print("交付前在浏览器里对每个页面运行 layout-check.js 和 spec-check.js：注入后执行 aiflowLayoutCheck()、aiflowSpecCheck()，输出都为空才算通过")
if preset:
    print("用了样式预设 %s：按 references/design-system.md「样式包和组件库对照」，用 _built.css 和真实组件库比一次，差异列进 03-design.md" % preset)
