# aiflow · AI 全流程交付工作流

一个 Agent Skill：把一句话需求推到上线。十二个阶段、八个角色。

- 需求分析师反复追问，直到没有遗留问题，再请你确认范围
- PRD、产品原型、设计稿都要你确认才往下走；你提的问题照着改，不清楚的继续问
- 需要设计稿时由体验设计师出稿；前端开发完，体验设计师走查页面，还原度 ≥ 90% 才算通过，不达标的点派回前端改，改完再走查
- 每个阶段收尾跑门禁脚本，漏项、编造编号、版本过期、没经确认都会被拦下

> 预览版：阶段 0–3（需求澄清到设计稿）在真实项目上跑过；阶段 4–11 目前只有门禁脚本的回归测试，还没在真实项目上跑通。

## 安装

用 [skills CLI](https://github.com/vercel-labs/skills)（需要 Node.js），可以装进 Claude Code、Codex、Cursor 等工具：

```bash
npx skills add SotherWind/aiflow
```

它会列出仓库里的 skill，问你装进哪个工具。也可以直接指定：`-a claude-code` 指定工具，`-g` 装到用户目录、所有项目都能用，`-y` 不再逐项确认。

不用 Node.js 时，把 `skills/aiflow/` 整个目录复制到所用工具的 skills 目录，目录名保持 `aiflow`：

- Claude Code：`~/.claude/skills/aiflow`
- WorkBuddy：`~/.workbuddy/skills/aiflow`

## 依赖

- Python 3：门禁脚本 `scripts/check.py` 和原型构建 `build.py` 只用标准库
- 浏览器自动化工具（如 Playwright）：原型和设计稿的版式检查、规范检查
- 网络：`scripts/parity/` 和真实组件库对照时从 unpkg 加载 Element Plus

## 怎么用

见 [skills/aiflow/README.md](skills/aiflow/README.md)（上手）和 [skills/aiflow/SKILL.md](skills/aiflow/SKILL.md)（完整规范）。

改了 skill 之后跑一遍测试：

```bash
python skills/aiflow/tests/test_check.py
```

## 许可证

[MIT](LICENSE)
