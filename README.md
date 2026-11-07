# aiflow · AI 全流程交付工作流

一套 Agent Skills：一个 aiflow 主控、八个可独立使用的专业角色。整套按十二阶段推进交付，也可以只安装需要的角色。

- 默认由主智能体沟通与调度，各专业角色使用独立子智能体；按阶段交接，前后端可在任务独立时并行，环境不支持时明确降级为角色切换
- 所有角色遇到待决事项都按决策树逐轮追问；先在对话中问清、确认共识，再统一整理问题台账、状态与阶段文档
- 提问前按需查证外部案例与成熟方案，带来源和取舍帮助用户决定；需求调研重点比较竞品、替代产品与开源实现
- PRD、产品原型、设计稿都要你确认才往下走；你提的问题照着改，不清楚的继续问
- 需要设计稿时先生成图片供用户评审，修改到确认后再按图制作 HTML，并用浏览器截图核对；前端开发完再走查实现与最终设计稿，还原度 ≥ 90% 且关键项通过才算通过
- 每个阶段收尾跑门禁脚本，漏项、编造编号、版本过期、没经确认都会被拦下
- 支持用户提供前端、后端开发规范 Markdown，也支持项目和团队默认规范；已配置就遵循，开发及修复都留检查记录
- 支持指定技术栈与框架；未指定部分主动推荐，已有项目优先建议沿用。展示组合、版本与取舍，用户确认后锁定，更换时重新确认
- 回退与变更显式登记失效产物，检查旧结果是否已重置；保留历史快照，重做后重新确认，未关闭问题要迁移或明确处置

> 预览版。真实试跑经过的路径与尚未验证的分支见 [验证范围](skills/aiflow/README.md#后续验证)。

## 安装

推荐通过通用 skills CLI 跨工具安装。它可以一次装齐主控和八个角色，无需使用宿主的插件市场；支持原生插件的工具也可以选择下方的插件入口。

### 跨工具整套安装（推荐）

使用 [skills CLI](https://github.com/vercel-labs/skills)（当前版本需要 Node.js 22.20+），根据当前环境检测安装目标：

```bash
npx skills add SotherWind/aiflow --skill '*'
```

需要指定工具时使用 `-a`，例如：

```bash
npx skills add SotherWind/aiflow --skill '*' -a cursor -y
npx skills add SotherWind/aiflow --skill '*' -a opencode -y
```

常见目标如下；将示例中的 `cursor` 或 `opencode` 换成相应标识即可。

| 工具 | `-a` 目标标识 |
| --- | --- |
| Codex | `codex` |
| Claude Code | `claude-code` |
| Cursor | `cursor` |
| OpenCode | `opencode` |
| Gemini CLI | `gemini-cli` |
| GitHub Copilot | `github-copilot` |
| Trae | `trae` |
| Windsurf | `windsurf` |

更多工具见 [skills CLI 支持列表](https://github.com/vercel-labs/skills/blob/main/docs/agents.md)。这张表列的是安装目标，宿主执行能力和项目实测情况见下方「兼容性与验证范围」。

默认装到当前项目；加 `-g` 才装到用户目录，`-y` 跳过安装确认。`--skill '*'` 选择全部九个技能；`--all` 还会选择所有工具，因此这里不使用它。

### 单角色安装与选择

按角色名称安装，`-a` 同样可以换成上表中的目标：

```bash
npx skills add SotherWind/aiflow --skill aiflow-frontend -a cursor -y
npx skills add SotherWind/aiflow --list
npx skills add SotherWind/aiflow
```

仅指定 `--skill aiflow` 只会安装主控，不会补装角色。主控开始执行前会检查八个角色、版本和资源完整性，缺项时给出补装提示。独立角色自带执行说明与所需资源，不依赖主控或其他角色；协作模式才读取主控的阶段协议。

### 原生插件整套安装（可选）

仓库提供开放 [Agent Plugins](https://agent-plugins.org/) 格式的根 `plugin.json`，以及 `.claude-plugin/` 兼容清单，两者分发同一组九个技能。下面列出 Codex 和 Claude Code 的具体入口；开放格式不限定这两个宿主。

Claude Code：

```bash
claude plugin marketplace add SotherWind/aiflow
claude plugin install aiflow@aiflow
```

Codex：

```bash
codex plugin marketplace add SotherWind/aiflow
codex plugin add aiflow@aiflow
```

也可以在宿主的插件目录中打开 `aiflow` 市场，安装同名插件。[Cursor 官方文档](https://cursor.com/docs/plugins)也说明支持根 `plugin.json` 的 Agent Plugins 格式；其插件安装入口与市场机制由 Cursor 提供，我们尚未实测该入口，可先使用上面的 `-a cursor` 通用安装方式。其他宿主按其官方支持的格式与安装入口操作，不直接照搬 Codex 或 Claude Code 命令。

### 本地版本与手工安装

远程命令获取仓库已发布的内容；开发中的本地版本可将命令里的 `SotherWind/aiflow` 换成当前仓库的绝对路径。

不用安装工具时，将 `skills/` 下全部九个技能目录复制到目标工具的技能目录；只用一个角色则只复制该角色目录，保留其中的参考资料、资源和 `role.json`。例如 Claude Code 使用 `~/.claude/skills/`，WorkBuddy 使用 `~/.workbuddy/skills/`。整套的九个目录应来自同一版本。

### 兼容性与验证范围

截至 2026-11-07，本项目已完成以下验证：

- 使用 `skills@1.7.6`、`-a codex --copy` 在 Windows 隔离目录实际安装整套、逐一单装八个角色，以及只装主控并检查缺失角色，共 10 个场景通过。这验证了文件分发与完整性，不代表其他宿主客户端都已实测。
- Claude 插件清单通过 `claude plugin validate`；根清单通过 Agent Plugins 1.0.0 JSON Schema 校验。Codex 与 Claude Code 的原生插件安装入口已提供，尚未在本轮向真实用户环境安装并验证整套插件运行。
- 在当前 Codex 环境完成前端单角色执行和需求角色接受主控派工的试跑；其他工具中的完整十二阶段流程尚待逐项验证。已有项目试跑覆盖范围见 [后续验证](skills/aiflow/README.md#后续验证)。

运行各阶段还需要宿主实际提供相应能力，见 [依赖](#依赖)。子智能体不可用时，可按流程说明使用模式 1 角色切换；生图或浏览器能力不足时，保留相应待完成检查，不能将安装成功当成阶段验证通过。

## 独立角色

| 技能 | 用途 |
| --- | --- |
| [aiflow-analyst](skills/aiflow-analyst/SKILL.md) | 需求澄清、范围协商、调研 |
| [aiflow-product](skills/aiflow-product/SKILL.md) | PRD、验收标准、产品原型 |
| [aiflow-design](skills/aiflow-design/SKILL.md) | 视觉设计、HTML 设计稿、走查 |
| [aiflow-architect](skills/aiflow-architect/SKILL.md) | 技术选型、架构、契约、任务拆分 |
| [aiflow-frontend](skills/aiflow-frontend/SKILL.md) | 前端开发、交互和页面缺陷修复 |
| [aiflow-backend](skills/aiflow-backend/SKILL.md) | 后端接口、数据操作、JOB |
| [aiflow-test](skills/aiflow-test/SKILL.md) | 测试、缺陷复测、回归 |
| [aiflow-release](skills/aiflow-release/SKILL.md) | 发布、回滚、观察与验证 |

例如在 Codex 中用 `$aiflow-frontend 修复订单列表筛选`，直接依据项目代码和任务工作；用 `$aiflow 做一个设备巡检系统` 才进入全流程。插件宿主可能为入口显示命名空间，以其技能列表为准。

## 依赖

- Python 3：门禁脚本 `scripts/check.py` 和原型构建 `build.py` 只用标准库
- 浏览器自动化工具（如 Playwright）：原型和设计稿的版式检查、规范检查
- 网络：`scripts/parity/` 和真实组件库对照时从 unpkg 加载 Element Plus
- 联网检索 / 网页读取工具：用于按需调研公开案例与方案；不可用或用户禁止联网时明确限制，不编造调研结论
- 图像生成与编辑能力：阶段 3 先出设计图、根据用户反馈改图；实际工具以运行环境为准，不用 HTML 截图替代
- 子智能体：能派子智能体时，各专业角色在独立上下文中执行。多角色往返的阶段（3、4、6、7、9）中，子智能体能再派一层就由阶段执行协调器派角色，不能就由主智能体直接派，并在 `state.yaml` 记录原因。不能派子智能体时用模式 1：在同一会话里切换角色，并如实说明

## 怎么用

见 [skills/aiflow/README.md](skills/aiflow/README.md)（上手）和 [skills/aiflow/SKILL.md](skills/aiflow/SKILL.md)（完整规范）。

## 维护与验证

`aiflow.bundle.json` 是版本、角色名单和资源分发的来源。角色的 `SKILL.md` 与 `references/aiflow.md` 直接维护；公共说明在 `shared/` 维护，原型工具仍在主控模板目录维护。修改后生成随包快照及插件清单：

```bash
python scripts/bundle_skills.py
python scripts/bundle_skills.py --check
```

生成结果提交到仓库，安装者无需执行构建。不要手工改角色里的生成资源或插件清单；先改源文件再生成，检查会识别内容和版本漂移。

修改后运行：

```bash
python -B tests/test_distribution.py
python skills/aiflow/tests/test_check.py
```

改动版式、规范检查脚本或组件对照时，还需跑 `skills/aiflow/tests/browser/` 的浏览器维护测试，安装和运行命令见 skill 上手文档。

## 许可证

[MIT](LICENSE)
