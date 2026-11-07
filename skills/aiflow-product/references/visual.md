# 独立原型与设计工具

本文件由 `scripts/bundle_skills.py` 从 `shared/visual.md` 分发。这里的资源都在当前角色技能内，独立使用无需安装主控。

用户指定工具、已有组件库和设计规范优先。需要轻量 HTML 原型时，可把 `templates/prototype-kit/` 复制到本次产物目录，例如 `<交付目录>/prototype/`，在 `_src/` 按 `_template.html` 编写页面，再运行复制后的 `build.py`。页面会内联样式。不要在已安装技能目录内编写项目页面或运行构建。

构建器可读取原型目录旁的 `design-system.md`。需要定制时，写带「变量」「取值」列的令牌表，使用 `_src/kit.css` 已定义的变量；例如 `--primary`、`--text`、`--radius`。使用 Element Plus 预设时写 `- 样式预设：element-plus`；没有规范文件时采用工具默认值，不创建 `.aiflow/`。页面内容、品牌取值及组件选择由本次任务决定。

交付前在浏览器实际打开每个必要页面和视口，验证布局、状态、交互、导航和可访问性，并保留真实截图。可向页面注入工具包的 `layout-check.js` 与 `spec-check.js`；具体调用为 `aiflowLayoutCheck()`、`aiflowSpecCheck()`。规范范围须来自用户已确认的规范或设计，不能从待测页面取值再自证合规；脚本通过也不代替视觉核对。

使用样式预设时，可用 `scripts/parity/kit.html`、`element-plus.html` 和 `parity.js` 对照真实组件库。真实库页面需要网络；不可用时记录未完成的比较。工具页面的相对目录已随技能一起打包，无需访问原仓库。

这些资源帮助构建和验证，不改变当前任务的交付形态。用户只要 PRD 时不自动做原型；只做现有页面走查时不要求重新生成设计图片。新建完整设计方案的图片评审、HTML 和复核顺序由设计角色说明。
