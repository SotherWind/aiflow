# 阶段与角色模型配置

项目存在 `.aiflow/models.json`、用户指定外部模型配置，或本次明确指定角色模型时读取本协议。适用于主控直接派工、协调器派工和独立评审。未配置时沿用宿主默认，不要求新增模型文件或历史模型记录。独立调用角色技能仍使用当前会话，加载技能本身不切换模型。

面向使用者的字段类型、默认值、完整示例、文件接入与生效检查见 [模型配置指南](../configuration.md#模型配置)；全部合法配置键及中文含义见 [角色与身份完整清单](../configuration.md#角色与身份完整清单)。可复制的 JSON 分为 [专业技能基础示例](../examples/models.json) 和 [覆盖全部 11 项的全量示例](../examples/models-advanced.json)。本页主要规定派工与执行记录。

## 配置与解析

按需从 `templates/models.json` 创建项目配置。模板的 `roles` 默认为空，只填写需要单独设置的角色。配置只含模型选择，不含密钥、地址或供应商凭据；可用模型与执行权限由当前宿主提供。以下模型 ID 是示意，使用时替换为宿主可核实的真实 ID：

```json
{
  "schema_version": 1,
  "default": "inherit",
  "profiles": {
    "coding": {"model": "<开发模型ID>"},
    "deep": {"model": "<复杂任务模型ID>", "reasoning_effort": "high"}
  },
  "roles": {
    "aiflow-frontend": "coding",
    "aiflow-backend": "coding",
    "aiflow-test": "deep"
  },
  "stages": {
    "6": {"roles": {"aiflow-backend": "deep"}},
    "9": {"default": "deep"}
  },
  "on_unavailable": "error"
}
```

选中一个完整 profile：**本次显式覆盖 → 阶段内角色 → 阶段默认 → 角色默认 → 项目默认**。默认 `inherit`，表示保留实际派工方的宿主默认选模规则，不传模型或推理强度覆盖；显式 `inherit` 会终止继续向下查找。协调器有专用模型而专业角色应使用另一默认时，配置项目默认或对应角色 profile。更换 profile 时一起替换模型和推理设置；未指定推理强度时不从较低优先级 profile 拼接，按所选模型与宿主的真实默认核对。

专业角色推荐填写与 `SKILL.md` 的 `name` 一致的完整技能名；原有内部角色键继续兼容。解析器从随包的 `roles.json` 读取映射。八个专业角色的完整名、兼容键，以及三个额外身份统一列在 [角色与身份完整清单](../configuration.md#角色与身份完整清单)，使用同一份清单核对，避免遗漏。

两种名称均可用于项目 `roles`、阶段内 `roles`，以及模型解析器的 `--role`、`--override`、`--model`、`--reasoning-effort`。同一个角色映射中同时填写 `fe` 与 `aiflow-frontend` 会报重复角色错误，即使值相同也不接受；不同配置层可使用不同名称，仍按上述优先级解析。

`coordinator`、`design_reviewer`、`final_reviewer` 是 `orchestration.md` 定义的额外会话身份，直接使用这些键，没有单独的技能目录，也不属于 `roles.json` 的八个专业技能安装项。模型解析器接受这些派工目标，角色安装解析器仍只检查专业技能。职责、启动时机及配置示例见 [额外调度身份说明](../configuration.md#额外调度身份进阶)。阶段键为字符串 `"0"` 至 `"11"`。未知字段、角色、profile、重复 JSON 键及非法类型会报错；模型 ID 与推理强度的支持范围以宿主为准，不在技能里硬编码模型名单。

角色安装仍用 `resolve_roles.py`。新阶段派工前，用模型解析器预览本次实际角色；需要协调器时一并列入：

```bash
python "<flow_root>/scripts/resolve_models.py" "<项目绝对路径>" --stage 6 --role coordinator --role aiflow-frontend --role aiflow-backend --execution 7
```

`--execution` 与本次 `session_log` 执行序号一致。只读查看可省略，不产生快照。外部配置加 `--config "<实际配置绝对路径>"`；后续阶段继续使用该路径，路径保存在快照 `config_path`，无需猜测用户目录。`--override aiflow-backend=deep` 临时选择已定义 profile；无配置文件时也可用 `--model aiflow-analyst=<实际模型ID>`，需要推理强度时同时给 `--reasoning-effort aiflow-analyst=high`。临时覆盖只作用于本次执行。

命令只读，输出 `configured`、每个角色的 `role_models`（`skill` 技能名、命中规则、请求值、`launch`）及可选 `snapshot`。解析结果、命中规则路径和快照统一使用内部角色键；例如 `role_models.fe.skill` 为 `aiflow-frontend`，调度身份的 `skill` 为 `null`。主控将这些内部键用于 `agent_sessions`、`session_log` 和 `model_runs.jsonl`，已有记录与快照无需迁移。

读取既有快照时 `snapshot_path` 明确指出本次来源；`config_path` 此时只记录快照的原配置来源，不表示重读了该文件。`ok: true` 只表示规则解析与已提供能力检查未阻塞，不证明启动或选模已实际发生。未知宿主能力显示 `unverified`；主控须在真实派工时继续核验。

宿主能力已查明时可通过 `--capabilities "<能力记录绝对路径>"` 预检：文件形如 `{"model_selection":true,"models":{"真实模型ID":{"reasoning_efforts":["high"]}}}`。名单必须来自当前宿主且适用于本次派工层级。未列 `models` 表示名单未知；已列的空对象表示没有可用模型；未列某模型的 `reasoning_efforts` 表示其推理支持未知。该记录不是宿主配置，也不授权或安装模型。

## 阶段快照与原生派工

1. 主控在新阶段确定执行序号，解析本次策略。`configured: true` 时保存返回的 **`snapshot` 对象**到 `.aiflow/model-policies/<执行序号>-<修订号>.json`，使用新文件名；它包含完整配置与覆盖、阶段和指纹。阶段 0 未收口时先保留在会话中，收口后才落文件，保持原来的先访谈规则。
2. 主控将快照路径、指纹和本角色的解析结果加入派工输入。协调器沿用同一快照为每个专业角色解析；派工方把 `launch` 中的选择通过宿主原生能力应用。只在任务提示中写模型名称不算选模。协调器自己的模型不替代角色已有的显式选择。
3. 支持创建时选模的宿主，将请求转换成其实际参数；通过预定义代理选模的宿主，核对该代理的最终模型与推理设置。遵循实际工具的历史隔离限制，不为选模继承上层聊天、扩大权限或修改用户全局配置。普通原生子智能体无法使用的供应商模型，不能靠一个名字获得执行能力。
4. 同阶段续派或新增条件角色，从保存的快照解析，避免重读已变更的配置：`resolve_models.py "<项目绝对路径>" --stage 6 --role aiflow-backend --snapshot "<快照绝对路径>"`。既有会话复用前核对其请求设置仍匹配；复用本身不会切换模型。
5. 返回真实会话 ID、派工结果、请求模型及可取得的运行元数据，由主控登记模型记录。执行协调器和专业角色只回传观察结果，不写模型快照、模型台账或机器状态。

模型不可用、原生能力无法实现或无法核实显式选模时，默认 `on_unavailable: error`，暂停受影响派工并说明实际原因；其他独立任务可继续。配置明确为 `inherit` 才可取消模型及推理覆盖，沿用宿主默认，记录具体限制、原始调用依据与实际回退。未知能力本身不触发静默回退；不能把失败的请求当成已创建会话。模型别名应先依据宿主的映射核实规范 ID；实际值与配置不能直接对应时保留未验证，更新为核实后的模型 ID 再派工。

模式 1 仅在当前会话切换角色。有显式模型要求时，策略须允许 `inherit`，并在 `model_policy.fallback_reason` 记录能力限制；不创建虚假的子智能体模型台账。仅继承的配置不要求模式 1 创建模型记录。

## 模型执行记录

主控保存当前策略索引，保持状态文件的一层结构：

```yaml
model_policy:
  snapshot: "model-policies/7-1.json"
  fingerprint: "<解析器返回的 snapshot.fingerprint>"
```

快照路径以 `.aiflow/` 为根且留在该目录内。模式 2/3 的实际结果追加到 `.aiflow/model_runs.jsonl`，每行一个 JSON 对象。以下展开仅用于展示字段，实际文件每条写在一行：

```json
{
  "schema_version": 1,
  "execution": 7,
  "stage": 6,
  "role": "be",
  "session_id": "<原生工具真实返回的ID>",
  "policy": "model-policies/7-1.json",
  "policy_fingerprint": "<对应快照指纹>",
  "requested_model": "<快照解析出的模型ID，inherit时为null>",
  "requested_reasoning_effort": "high",
  "actual_model": null,
  "actual_reasoning_effort": null,
  "verification": "unverified",
  "dispatch_evidence": "<实际创建调用、返回和后续任务依据>",
  "model_evidence": "<宿主未返回模型元数据的具体情况>",
  "fallback_reason": "",
  "created_at": "2026-11-16T12:00:00+08:00"
}
```

`requested_model` / `requested_reasoning_effort` 逐项复制该角色解析值，没有设置就用 JSON `null`。`actual_model` 使用宿主返回或运行元数据中的规范模型 ID，不能复制请求值、依据角色名推测，或采信子智能体对自身模型的猜测。无法核实就保持两项实际值为 `null`、`verification: unverified`；能核实模型时设 `verified` 并给 `model_evidence`，推理强度仍未知则单独为 `null`。`created_at` 是实际记录时间且含时区。

初次未知、后来查得元数据时追加新观察，保留旧行。已知实际模型或推理设置改变须使用新会话。每条日志关联自身快照，历史快照留在原路径；配置指纹只能检出内容变化，不能证明工具调用或模型元数据真实。

门禁检查当前必需角色、已完成额外派工和协调器的会话覆盖、执行序号、请求与快照一致性，以及显式请求的实际模型和推理强度；获准回退须有逐会话原因。继承且未要求具体模型的角色允许如实标记未验证；显式模型尚未核实不能声称配置成功。`session_log` 和模型台账均只追加，同一会话不能跨执行、跨角色或换模型复用。旧项目无模型配置与索引时兼容，不追补过去的执行事实。

启用模型策略后的模式 3，如采用不同模型终验：`agent_sessions.final_reviewer` 仍是 `model:<实际规范模型ID>`，新增顶层 `final_review_session` 保存真实终验会话 ID；模型日志中另记 `role: final_reviewer`，不把模型标签充当会话 ID，也不改原 `session_log` 的角色格式。校验终验的实际模型与各执行角色最近登记的实际模型不同，包含当前协调器；任一需要比较的模型未知时，不能证明不同模型终验。阶段 11 可沿用仍有效且属于最近一次阶段 10 执行的终验记录，重新执行阶段 10 或终验失效时须重做。人工终验沿用 `human:<姓名>` 与已有证据，不要求模型会话。

## 换模、回退与状态查询

配置文件修改在下一次进入阶段时重新解析。同阶段明确要求换模时，主控保留旧快照，生成同执行序号的新修订快照；更换模型或推理强度的角色新建会话、重新派工，清除其旧完成项并记录替换依据，未改变请求设置的角色可沿用原会话及原快照日志。专业结果是否需要重做由任务影响决定，纯换模不提升 facts 版本。

换阶段、回退、重新进场重做时使用新执行序号与新会话，重置 `model_policy` 当前索引，再从项目配置或用户选定的外部路径生成新快照。跳过阶段清除当前索引；保留全部历史快照和模型日志。终验失效时同时清空 `final_review_session`。新阶段明确停用模型配置时移除当前索引、保留历史并记录原因；不能在当前执行中删除配置来绕过已有快照。

查询模型状态时展示阶段、角色、命中规则、请求模型、已核实的实际模型或未验证原因，以及回退情况。运行中展示快照所约束的值；磁盘配置的预览属于下次执行，不把二者混为已生效状态。只读预览不创建 `.aiflow/`、不要求补装角色，也不触发真实派工。
