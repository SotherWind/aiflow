# 设计规范怎么设置

适用：需要产品原型或设计稿的项目。阶段 2 由产品经理确定，原型图、设计稿、前端开发共用。不需要原型和设计稿的项目，不用设置。

## 一、记在哪

| 位置 | 放什么 | 谁维护 |
|---|---|---|
| `<项目>/.aiflow/design-system.md` | 本项目实际采用的规范。**这是唯一的记录**，原型、设计、开发都读它 | 产品经理在阶段 2 写，随 PRD 一起确认 |
| `~/.aiflow/design-system.md`（Windows 是 `C:\Users\<用户名>\.aiflow\design-system.md`） | 团队默认规范。写一次，以后的项目复制过去用 | 团队自己维护 |

两份都用 `templates/design-system.md` 的格式。团队级文件放在 skill 目录外面，skill 换项目、升级时都不用改。

## 二、阶段 2 按顺序找

1. 项目里已经有 `.aiflow/design-system.md`：沿用。
2. 项目已经有前端代码：读 `package.json` 和主题配置（例如 antd 的 `ConfigProvider` 主题、Element Plus 的 CSS 变量、TDesign 的主题文件），取出组件库和设计令牌。这是查得到的事实，不问用户。
3. 用户给了规范文件（令牌文件、规范文档、典型页面截图）：读文件，把路径写进「规范文件」。
4. 有团队级 `~/.aiflow/design-system.md`：复制过来，来源写「团队默认规范」。交付项目常有甲方自己的规范，所以这一条是「按默认处理」，要在 PRD 评审时让用户看到、能改。
5. 以上都没有：先在对话中问用户这个项目有没有要遵守的设计规范或组件库。用户答「没有」时，提出默认方案；问清并形成共识后，再归档问题与采用的规范来源。

确定后写进 `.aiflow/design-system.md`，并在 PRD 的「交付形态判断」里写一行「设计规范」，随 PRD 一起确认。

## 三、规范怎么交给 AI

| 规范在哪 | 怎么做 |
|---|---|
| 项目的前端代码里 | 不用给，AI 自己读 |
| 令牌文件、规范文档、截图 | 放进项目目录（例如 `docs/design/`），在「规范文件」里写路径 |
| Figma、墨刀、MasterGo、内网站点 | AI 一般打不开：导出令牌，或者截几张典型页面放进项目目录。配了 Figma 的 MCP 连接器时，可以直接给链接 |

## 四、原型样式包怎么用它

`templates/prototype-kit/build.py` 构建时按顺序拼接样式：

1. `kit.css`：Ant Design 默认主题
2. 样式预设 `_src/presets/<名>.css`（design-system.md 写了「样式预设」时）：某个组件库的默认令牌和结构差异
3. `.aiflow/design-system.md` 令牌表里「取值」不是「按默认」的行，覆盖同名的 CSS 变量。改了主色、成功、警告、错误、信息色时，浅色背景、描边和文字色自动派生；派生比例按预设，没有预设时按 Ant Design
4. `_src/theme.css`（如果有）：令牌表和预设都表达不了的差异写在这里

构建时会列出覆盖了哪些令牌；令牌名写错、样式包里没有的，也会提示。拼好的完整样式另存为 `_built.css`，组件库对照时用。

### 常见组件库的变量怎么对应

规范文件里的变量名各家不同，按含义对到样式包的变量上。样式包支持的全部变量见 `prototype-kit/_src/kit.css` 的 `:root`。

| 样式包变量 | Element Plus | Ant Design 5 主题令牌 |
|---|---|---|
| `--primary` | `--el-color-primary` | `colorPrimary` |
| `--primary-bg` / `--primary-bd` | `--el-color-primary-light-9` / `-light-8` | `colorPrimaryBg` / `colorPrimaryBorder` |
| `--success` / `--warning` / `--error` | `--el-color-success` / `-warning` / `-danger` | `colorSuccess` / `colorWarning` / `colorError` |
| `--text` / `--text2` / `--text3` | `--el-text-color-primary` / `-regular` / `-secondary` | `colorText` / `colorTextSecondary` / `colorTextTertiary` |
| `--text-dis` | `--el-text-color-placeholder` | `colorTextPlaceholder` |
| `--border` / `--split` | `--el-border-color` / `--el-border-color-lighter` | `colorBorder` / `colorSplit` |
| `--fill` / `--fill-dis` | `--el-fill-color-light` | `colorFillAlter` / `colorBgContainerDisabled` |
| `--layout` / `--surface` | `--el-bg-color-page` / `--el-bg-color` | `colorBgLayout` / `colorBgContainer` |
| `--radius` / `--radius-lg` / `--radius-sm` | `--el-border-radius-base`（三个都对它） | `borderRadius` / `borderRadiusLG` / `borderRadiusSM` |
| `--radius-checkbox` | `--el-border-radius-small` | `borderRadiusSM` |
| `--info` / `--info-bg` / `--info-bd` | `--el-color-info` / `-light-9` / `-light-8` | 无对应，没有类型的标签用中性色 |
| `--font` / `--font-size` | `--el-font-family` / `--el-font-size-base` | `fontFamily` / `fontSize` |
| `--header-h` | `--el-header-height` | `Layout.headerHeight` |
| `--mask-bg` | `--el-overlay-color-lighter` | `colorBgMask` |
| `--avatar-bg` | `--el-avatar-bg-color` | `colorTextPlaceholder` |

> `--radius-sm` 是样式包里小按钮、标签、骨架屏的圆角。Element Plus 的这些组件用基础圆角，只有复选框用小圆角，所以 `--el-border-radius-small` 对到 `--radius-checkbox`，不要对到 `--radius-sm`，否则按钮和标签会变成 2px。

### 样式预设

规范基于常见组件库时，在 design-system.md 的「样式预设」写预设名，构建时自动套用它的默认令牌和结构差异，不用自己写 theme.css：

| 预设 | 适用 | 包含 |
|---|---|---|
| `element-plus` | 基于 Element Plus 2.x 的规范 | Element Plus 默认色板与派生比例，以及按钮、输入框、表单、表格、页签、分页、卡片、弹窗、提示条、消息提示、步骤条、时间轴、结果、空状态、描述列表、面包屑等组件的默认尺寸和样式；图标用 Element Plus 图标库。和 element-plus 2.14.7 逐项对照过（70 项一致，2026-11-01） |

用了预设，令牌表只需要写和预设默认值不同的项（例如改了主色）。预设只放组件库默认的样子；规范和组件库默认不一样的地方写进 `_src/theme.css`，并列进 `03-design.md`「实现时要改组件库默认值的地方」。要支持新的组件库，照 `presets/element-plus.css` 加一个文件，并按下面「样式包和组件库对照」对照到差异为空。

### 状态标签用语义类

状态标签用 `tag primary / success / warning / danger / info` 五个语义类，不用 `tag blue / orange` 这类颜色类。每个状态用哪种类型，写在 design-system.md 第四节「状态与标签类型」；换规范时只换颜色，不用改页面。颜色类只留给规范明确要求某种颜色、又不属于这五种语义的地方。

页面里不要用行内 `style` 写死颜色：行内颜色不走变量，换规范时不会跟着变。构建时会提示哪些页面写死了颜色。

规范和 Ant Design 的风格差得很远（例如移动端、大屏）时，不硬套样式包：用规范自带的组件库在墨刀或 Figma 里画原型，页面编号和说明仍然写在 `02-prototype.md`。

### 规范检查的取值范围

`spec-check.js` 从页面的 `:root` 读允许的取值：颜色是 `:root` 里的全部颜色变量，字号、圆角、控件高度是 `--check-font-sizes`、`--check-radii`、`--check-btn-heights`、`--check-input-heights`、`--check-tag-heights`，字体是 `--font`。样式包和预设给了默认范围；规范定得更细时（例如只允许 12、13、14、16、18、20px），在 design-system.md 令牌表加这几行覆盖。阴影和间距不查，靠走查点和评审。

### 样式包和组件库对照

样式包是照组件库仿出来的。仿错一处，所有原型和设计稿都跟着错，前端用真组件库实现时处处对不上。对照工具在 `scripts/parity/`：`kit.html` 用样式包画出常用组件，`element-plus.html` 用固定版本的真实 Element Plus（CDN）渲染同样的组件，`parity.js` 逐个比较高、宽、圆角、背景、边框、阴影、字号、字重、颜色、行高、文字位置和间距。

维护检查脚本、样式包或对照页面时，另跑 `README.md` 的浏览器维护测试；它用锁定的本地依赖验证真实组件和故意引入的差异。升级对照基线时同步页面与测试依赖，并重新验证，不改成浮动版本。

用法：在 skill 目录起一个 http 服务（例如 `python -m http.server 8766`），用浏览器工具：

1. 打开 `scripts/parity/kit.html?preset=element-plus`，等 `window.__ready` 为 true，注入 `parity.js`，`A = aiflowParityMeasure('kit')`
2. 打开 `scripts/parity/element-plus.html`，等 `window.__ready` 为 true，注入 `parity.js`，`B = aiflowParityMeasure('element-plus')`
3. `aiflowParityCompare(A, B)` 返回差异列表

| 比的是 | 地址 | 差异应该是 | 有差异时 |
|---|---|---|---|
| 样式预设 | `kit.html?preset=element-plus` | 空 | 改预设，直到为空；更新预设开头的对照版本和日期 |
| 项目设计稿 | `kit.html?css=<设计稿 _built.css 的地址>` | 只剩规范要求的 | 每条要么改设计稿，要么写进 `03-design.md`「实现时要改组件库默认值的地方」并写明依据 |

- 规范没写、组件库有默认值的，按组件库默认，不要自己定一个数。
- 组件库自己的现象不算问题。例如 Element Plus 弹窗的关闭图标比按钮中心高 2px，`layout-check.js` 在真实组件上也会报；设计稿照画，走查时也不算前端的问题。
- 两边在同一个浏览器、同一个缩放下量。系统缩放 125%、150% 时 1px 边框会画成 0.8px、0.67px，脚本已经按整像素补回。
- 不用预设（Ant Design 默认样式）时，目前没有对照页面：`03-design.md` 的「组件库对照」写「未对照」，评审时告诉用户。

## 五、对下游的影响

| 环节 | 有规范 | 没有规范（按默认） |
|---|---|---|
| 原型图（阶段 2） | 用规范的令牌和组件 | Ant Design 默认主题 |
| 设计稿（阶段 3） | 生图与 HTML 都遵循已有规范；先确认图片，再按图制作 HTML | 体验设计师先生成视觉方案图片，用户确认后将采用的视觉落实为令牌与 HTML |
| 技术架构（阶段 4） | 规范声明了组件库时，前端选型要能用它；用不了，写明理由并请用户确认 | 原型用 Ant Design 的样式，不等于前端必须用 Ant Design |
| 前端开发（阶段 6） | 用规范的组件库和令牌 | 按设计稿 |

## 六、门禁

需要原型或设计稿的项目，阶段 2 起 `.aiflow/design-system.md` 必须存在，「来源」必须填写。阶段 3 先完成图片生成、评审与确认；进入 HTML 制作后，阶段收尾的 `03-design.md` 才需要完整设计稿自检。图片评审期间不提前要求 HTML 检查结果。
