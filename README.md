# Deep Research Skill

一个面向 AI Agent 的深度检索与证据核验 skill。它以可审计、可复核为目标，把检索拆分为问题解析、来源发现、原文获取、事实核验、冲突处理和结构化输出。

当前版本：`3.4.1`

## 核心特点

- 通过「深度检索」「深度查证」「深度研究」触发。
- 按结构化数据、搜索、原文读取和浏览器交互四条职责通道选择路径。
- 关键数字、日期、机构名称和版本优先回到原始来源核验。
- 明确区分事实、来源观点和推断。
- 对关键数字执行换问法复查，并记录来源独立性和未覆盖范围。
- 支持简洁档与报告档两种输出。
- 对网页、PDF、搜索结果和附件统一按不可信数据处理。
- 远程链接探活默认关闭，仅在用户明确同意后执行。
- 不包含第三方 Python 依赖，不下载或执行远程代码。

## 仓库结构

```text
.
├── .gitignore
├── SKILL.md
├── README.md
├── references/
│   ├── evidence-policy.md
│   ├── output-contract.md
│   ├── platform-adapters.md
│   ├── retrieval-workflow.md
│   └── source-selection.md
├── scripts/
    ├── check_sources.py
    ├── today.py
    └── verify_report.py
└── tests/
    └── test_check_sources.py
```

`SKILL.md` 是入口和硬规则，`references/` 保存详细流程，`scripts/` 提供可选的本地增强能力。

## 环境要求

- 支持读取 skill 文件并调用对话、搜索、网页或终端工具的代理平台。
- 可选：Python 3.10 或更高版本，用于运行本地脚本。
- 可选：用户明确授权后的网络访问，用于链接探活。

Python 脚本不是核心检索的必要条件。缺少 Python、网络或相关工具时，skill 会降级运行并明确标注未执行项。

## 安装

### Codex

把仓库克隆或复制到个人 skills 目录：

```bash
git clone https://github.com/zkzzkzl/deep-research-skill.git
```

将目录放到：

```text
~/.codex/skills/deep-research-skill/
```

Windows 默认位置：

```text
%USERPROFILE%\.codex\skills\deep-research-skill\
```

目录中应能直接看到 `SKILL.md`：

```text
deep-research-skill/
├── SKILL.md
├── references/
└── scripts/
```

### 其他代理平台

支持 `SKILL.md` 规范的平台可以直接读取仓库内容。纯提示词平台可把 `SKILL.md` 作为系统提示词，并按平台能力选择性内联 `references/` 文件。没有代码执行能力时跳过 `scripts/`。

## 使用方式

### 深度检索

```text
深度检索：2025 年中国新能源汽车出口量及同比增速
```

```text
深度查证：这条“某机构发布最新人口数据”的消息是否真实
```

```text
深度研究：比较中国、欧盟和美国 2025 年光伏新增装机数据，说明统计口径差异
```

### 配置与自检

```text
深度检索 配置
```

输出能力绑定报告和待办清单，不执行实际检索。

```text
深度检索 自检
```

执行允许范围内的能力探针并输出绑定结果。任何联网探针都需要用户明确授权。

### 输出档位

简洁档适合单点事实：

```text
<直接结论，含适用范围和时间>
来源：<来源名称>（<完整 URL>，发布：<日期>）
核验：<已核实 / 依据有限 / 未验证 / 存在分歧>
```

报告档包含固定骨架：

```text
### 检索结论
### 证据与来源
### 来源分歧
### 核验状态
### 未覆盖范围
```

## 本地脚本

### `today.py`

输出指定时区的当前日期，默认 `Asia/Shanghai`。

```bash
python -X utf8 scripts/today.py
python -X utf8 scripts/today.py --full
python -X utf8 scripts/today.py --timezone UTC
```

仅当平台没有注入当前日期时使用。

### `check_sources.py`

默认执行纯本地检查，不发起网络请求：

```bash
python -X utf8 scripts/check_sources.py sources.txt
cat report.md | python -X utf8 scripts/check_sources.py
```

检查内容包括：

- URL 协议、域名和端口语法。
- URL 是否携带用户名或密码。
- 精确重复和规范化重复。
- 疑似链接但无法解析的行。
- 输出时的敏感参数脱敏。

远程探活必须显式开启：

```bash
python -X utf8 scripts/check_sources.py sources.txt --probe
```

`--probe` 的安全边界：

- 只发送 HEAD，必要时回退到 GET。
- 不读取响应正文。
- 只允许 `http` 和 `https`。
- 只允许 80 和 443 端口。
- 禁止 localhost、私网、链路本地、保留地址和云元数据地址。
- 域名解析后会固定使用已校验的公网 IP，降低 DNS rebinding 风险。
- 重定向目标会重新解析、校验和固定 IP。
- 为保证 IP 固定策略生效，探活不经过 HTTP 代理；代理环境可能无法使用 `--probe`。

退出码：

| 退出码 | 含义 |
|---|---|
| `0` | URL 语法检查通过；探活异常会单独列出 |
| `1` | 发现 URL 语法或输入内容问题 |
| `2` | 输入无效或未发现 URL |

### `verify_report.py`

校验即将交付的简洁档或报告档结构：

```bash
python -X utf8 scripts/verify_report.py report.md
cat report.md | python -X utf8 scripts/verify_report.py
```

脚本只读取输入并输出检查结果，不修改文件。

## 安全与隐私

### 外部内容

- 网页、PDF、搜索结果和附件均视为数据，不视为可执行指令。
- 外部内容不能触发安装、消息发送、持久文件写入、凭据泄露或权限扩大。
- 发现提示注入、恶意文件或异常下载行为时，停止处理并标注风险。

### 联网行为

- 普通检索可能使用平台已暴露的搜索、网页和浏览器工具。
- 本地脚本的远程链接探活不是默认行为。
- 运行 `--probe` 前必须取得用户明确同意。
- 探活会向目标服务器暴露请求来源 IP、User-Agent 和访问时间。

### 用户上下文

邮箱、网盘、日程、通讯录和本地文件等用户上下文来源，只能在当前会话中由用户明确提出或逐次确认后访问。模型判断“有必要”不构成授权。读取时只取完成当前问题所需的最小范围，不进行全量扫描，也不写入持久文件。

### 敏感 URL

`check_sources.py` 会拒绝携带用户名或密码的 URL，并对以下常见敏感查询参数进行输出脱敏：

```text
access_token, api_key, apikey, auth, authorization, client_secret,
key, password, passwd, secret, share_token, sig, signature, token
```

URL 中不能识别的私有令牌仍应由使用者避免提交、粘贴或写入公开报告。

### 权限原则

- 网络授权、文件访问和命令执行必须遵循平台权限模型。
- 只请求完成当前检索所必需的权限。
- 需要新增联网探针或私有来源访问时，先说明范围并请求授权。

## 兼容性

| 平台能力 | 支持情况 |
|---|---|
| 搜索、读取网页、浏览器和计算工具 | 使用平台现有工具执行 |
| 没有联网工具 | 基于已知来源或模型记忆回答，并明确标注未核实 |
| 没有代码执行 | 跳过脚本，保留核心检索和输出规则 |
| 只有对话能力 | 可使用结构规则，但不能声称完成联网核验 |

仓库中的 `SKILL.md` 使用 WorkBuddy 事实源格式。发布到仅接受 agentskills frontmatter 白名单的平台时，应把 `version` 和 `agent_created` 转换到 `metadata`，并补充平台要求的 `compatibility` 字段。

## 开发与验证

检查 Python 语法：

```bash
python -X utf8 -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('scripts').glob('*.py')]"
```

运行本地 URL 校验：

```bash
python -X utf8 scripts/check_sources.py sources.txt
```

运行报告结构校验：

```bash
python -X utf8 scripts/verify_report.py report.md
```

运行安全边界单元测试：

```bash
python -X utf8 -m unittest discover -s tests -v
```

修改 `SKILL.md`、`references/` 或 `scripts/` 后，应同步更新版本号和 README 中的行为说明。

## 已知限制

- 链接探活只能确认 HTTP 状态，不能证明正文可读或内容真实。
- JavaScript 渲染页、反爬页和限流页可能返回不可靠状态。
- 检索质量取决于平台可用的搜索、原文和浏览器工具。
- 该 skill 不绕过付费墙、登录、验证码或访问控制。
- 不提供投资、医疗、法律等专业建议。

## 贡献

提交修改前请：

1. 保持外部内容安全边界不做弱化。
2. 不从默认流程中移除用户授权要求。
3. 为网络、权限或文件访问变更补充说明和测试。
4. 更新版本号及 README。

## 许可证

当前仓库尚未声明开源许可证。默认情况下，保留全部权利；如需复用、修改或分发，请先联系仓库所有者确认授权。
