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
5. 以上都没有：在问题台账登记一个问题，问用户这个项目有没有要遵守的设计规范或组件库。有没有规范是查不到的事，不能直接按默认。用户答「没有」，来源写「无，按 Ant Design 默认主题」，依据写问题编号。

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

构建时会列出覆盖了哪些令牌；令牌名写错、样式包里没有的，也会提示。

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

> `--radius-sm` 是样式包里小按钮、标签、骨架屏的圆角。Element Plus 的这些组件用基础圆角，只有复选框用小圆角，所以 `--el-border-radius-small` 对到 `--radius-checkbox`，不要对到 `--radius-sm`，否则按钮和标签会变成 2px。

### 样式预设

规范基于常见组件库时，在 design-system.md 的「样式预设」写预设名，构建时自动套用它的默认令牌和结构差异，不用自己写 theme.css：

| 预设 | 适用 | 包含 |
|---|---|---|
| `element-plus` | 基于 Element Plus 2.x 的规范 | 默认色板与派生比例（浅 9 背景、浅 8 描边、文字用类型色）、白色顶栏、菜单下划线、卡片描边无阴影、表头白底、标签尺寸、无描边提示条、消息提示、带背景分页、实心时间轴、弹窗与浮层阴影、朴素危险按钮、圆角 |

用了预设，令牌表只需要写和预设默认值不同的项（例如改了主色）。预设之外还对不上的差异，写进 `_src/theme.css`。要支持新的组件库，照 `presets/element-plus.css` 加一个文件。

### 状态标签用语义类

状态标签用 `tag primary / success / warning / danger / info` 五个语义类，不用 `tag blue / orange` 这类颜色类。每个状态用哪种类型，写在 design-system.md 第四节「状态与标签类型」；换规范时只换颜色，不用改页面。颜色类只留给规范明确要求某种颜色、又不属于这五种语义的地方。

页面里不要用行内 `style` 写死颜色：行内颜色不走变量，换规范时不会跟着变。构建时会提示哪些页面写死了颜色。

规范和 Ant Design 的风格差得很远（例如移动端、大屏）时，不硬套样式包：用规范自带的组件库在墨刀或 Figma 里画原型，页面编号和说明仍然写在 `02-prototype.md`。

## 五、对下游的影响

| 环节 | 有规范 | 没有规范（按默认） |
|---|---|---|
| 原型图（阶段 2） | 用规范的令牌和组件 | Ant Design 默认主题 |
| 设计稿（阶段 3） | 按规范出稿，只补齐规范没覆盖的部分，不另起视觉 | 体验设计师提视觉方案，评审时请用户确认 |
| 技术架构（阶段 4） | 规范声明了组件库时，前端选型要能用它；用不了，写明理由并请用户确认 | 原型用 Ant Design 的样式，不等于前端必须用 Ant Design |
| 前端开发（阶段 6） | 用规范的组件库和令牌 | 按设计稿 |

## 六、门禁

需要原型或设计稿的项目，阶段 2 起 `.aiflow/design-system.md` 必须存在，「来源」必须填写。`check.py` 会查。
