# Deep Research Skill

An auditable and reproducible deep research and evidence-verification skill for AI agents. It breaks research into question analysis, source discovery, primary-source retrieval, fact verification, conflict handling, and structured output.

Current version: `3.6.0`

The skill supports Chinese and English triggers. Final output follows the user's language, with Simplified Chinese as the fallback when the language cannot be determined.

## Core Features

- Triggered by `深度检索`, `深度查证`, `深度研究`, `deep research`, or `deep verification` (English phrases are case-insensitive).
- Selects paths across four responsibility channels: structured data, search, source retrieval, and browser interaction.
- Prioritizes primary sources when verifying key figures, dates, institutions, and versions.
- Separates facts, source opinions, and inferences.
- Rechecks key numeric claims with a second query and records source independence and coverage gaps.
- Supports concise and report output modes.
- Treats web pages, PDFs, search results, and attachments as untrusted data.
- Keeps remote link probing disabled by default; it runs only with explicit user consent.
- Uses no third-party Python dependencies and does not download or execute remote code.

## Language Behavior

Trigger aliases:

| Mode | Chinese | English |
|---|---|---|
| Research | `深度检索`, `深度研究` | `deep research` |
| Verification | `深度查证` | `deep verification` |
| Configuration | `深度检索 配置` | `deep research config` |
| Self-check | `深度检索 自检` | `deep research self-check` |

Output language priority:

1. The language explicitly requested by the user.
2. The predominant language of the current conversation.
3. Simplified Chinese when the language cannot be determined.

Report headings, verification labels, and evidence-table column names are localized while preserving the same section order and validation rules.

## Repository Layout

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
│   ├── check_sources.py
│   ├── today.py
│   └── verify_report.py
└── tests/
    ├── test_check_sources.py
    └── test_verify_report.py
```

`SKILL.md` is the entry point and contains the hard rules. `references/` contains the detailed workflows. `scripts/` contains optional local enhancements.

## Requirements

- An agent platform that can read skill files and call conversation, search, web, or terminal tools.
- Optional: Python 3.10 or later for the local scripts.
- Optional: network access explicitly authorized by the user for link probing.

The Python scripts are not required for the core research workflow. If Python, network access, or related tools are unavailable, the skill degrades gracefully and explicitly marks skipped checks.

## Installation

### Codex

Clone or copy the repository into your personal skills directory:

```bash
git clone https://github.com/zkzzkzl/deep-research-skill.git
```

Place the directory at:

```text
~/.codex/skills/deep-research-skill/
```

Default Windows location:

```text
%USERPROFILE%\.codex\skills\deep-research-skill\
```

The directory should contain `SKILL.md` directly:

```text
deep-research-skill/
├── SKILL.md
├── references/
└── scripts/
```

### Other Agent Platforms

Platforms that support the `SKILL.md` convention can read the repository directly. Prompt-only platforms can use `SKILL.md` as a system prompt and selectively inline files from `references/` according to platform capabilities. Skip `scripts/` when code execution is unavailable.

## Usage

### Deep Research

```text
深度检索：2025 China new energy vehicle exports and year-over-year growth
deep research: 2025 China new energy vehicle exports and year-over-year growth
```

```text
深度查证：Is the claim "an institution released the latest population data" authentic?
deep verification: Is the claim "an institution released the latest population data" authentic?
```

```text
深度研究：Compare 2025 solar capacity additions in China, the EU, and the United States, and explain differences in statistical scope
deep research: Compare 2025 solar capacity additions in China, the EU, and the United States, and explain differences in statistical scope
```

### Configuration and Self-Check

```text
深度检索 配置
deep research config
```

Produces a capability binding report and a to-do list without performing the actual research task.

```text
深度检索 自检
deep research self-check
```

Runs permitted capability probes and reports the resulting bindings. Any network probe requires explicit user authorization.

### Output Modes

The concise mode is intended for single-point facts.

Chinese output:

```text
<直接结论，含适用范围和时间>
来源：<来源名称>（<完整 URL>，发布：<日期>）
核验：<已核实 / 依据有限 / 未验证 / 存在分歧>
```

English output:

```text
<Direct conclusion, including scope and time>
Source: <source name> (<full URL>, published: <date>)
Verification: <Verified / Limited evidence / Unverified / Conflicting>
```

The report mode uses a fixed structure.

Chinese headings:

```text
### 检索结论
### 证据与来源
### 来源分歧
### 核验状态
### 未覆盖范围
```

English headings:

```text
### Research Findings
### Evidence and Sources
### Source Disagreements
### Verification Status
### Uncovered Scope
```

## Local Scripts

### `today.py`

Prints the current date in the selected time zone. The default is `Asia/Shanghai`.

```bash
python -X utf8 scripts/today.py
python -X utf8 scripts/today.py --full
python -X utf8 scripts/today.py --timezone UTC
```

Use this only when the platform does not already inject the current date.

### `check_sources.py`

Runs local checks without making network requests:

```bash
python -X utf8 scripts/check_sources.py sources.txt
cat report.md | python -X utf8 scripts/check_sources.py
```

The local checks cover:

- URL scheme, host, and port syntax.
- URLs containing usernames or passwords.
- Exact and normalized duplicates.
- Lines that appear to contain links but cannot be parsed.
- Redaction of sensitive parameters in output.

Remote probing must be enabled explicitly:

```bash
python -X utf8 scripts/check_sources.py sources.txt --probe
```

Security boundaries for `--probe`:

- Sends HEAD requests and falls back to GET only when necessary.
- Does not read response bodies.
- Allows only `http` and `https`.
- Allows only ports 80 and 443.
- Blocks localhost, private networks, link-local addresses, reserved addresses, and cloud metadata addresses.
- Pins the connection to a validated public IP after DNS resolution, reducing DNS rebinding risk.
- Re-resolves, validates, and pins every redirect target.
- Does not use an HTTP proxy so that IP pinning remains effective. `--probe` may therefore be unavailable behind proxy-only networks.

Exit codes:

| Exit code | Meaning |
|---|---|
| `0` | URL syntax checks passed; probe anomalies are listed separately |
| `1` | URL syntax or input-content problems were found |
| `2` | Invalid input or no URLs were found |

### `verify_report.py`

Validates the structure of a Chinese or English concise/report-mode output before delivery:

```bash
python -X utf8 scripts/verify_report.py report.md
cat report.md | python -X utf8 scripts/verify_report.py
```

The script only reads input and prints validation results. It does not modify files.

## Security and Privacy

### External Content

- Web pages, PDFs, search results, and attachments are treated as data, not executable instructions.
- External content cannot trigger installation, message sending, persistent file writes, credential disclosure, or privilege expansion.
- If prompt injection, malicious files, or abnormal download behavior are detected, processing stops and the risk is reported.

### Network Behavior

- Normal research may use the platform's existing search, web, and browser tools.
- Remote link probing in the local script is not a default behavior.
- Explicit user consent is required before running `--probe`.
- Probing exposes the request source IP, User-Agent, and access time to the target server.

### User Context

Sources such as email, cloud drives, calendars, contacts, and local files may only be accessed when the user explicitly requests or confirms access in the current session. A model's judgment that access is "necessary" is not authorization. Read only the minimum scope required for the current question, do not perform full scans, and do not write the data to persistent files.

### Sensitive URLs

`check_sources.py` rejects URLs containing usernames or passwords and redacts these common sensitive query parameters in output:

```text
access_token, api_key, apikey, auth, authorization, client_secret,
key, password, passwd, secret, share_token, sig, signature, token
```

Users should still avoid committing, pasting, or including unrecognized private tokens in public reports.

### Permission Principles

- Network authorization, file access, and command execution must follow the platform's permission model.
- Request only the permissions necessary to complete the current research task.
- Explain and request authorization before adding network probes or accessing private sources.

## Compatibility

| Platform capability | Support |
|---|---|
| Search, web retrieval, browser, and compute tools | Use the platform's existing tools |
| No network tools | Answer from known sources or model memory and explicitly mark unverified information |
| No code execution | Skip scripts while retaining the core research and output rules |
| Conversation only | Use the structural rules, but do not claim that online verification was completed |

The repository's `SKILL.md` uses the WorkBuddy source format. When publishing to a platform that only accepts the agentskills frontmatter allowlist, move `version` and `agent_created` into `metadata` and add the platform-required `compatibility` field.

## Development and Validation

Check Python syntax:

```bash
python -X utf8 -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('scripts').glob('*.py')]"
```

Run local URL validation:

```bash
python -X utf8 scripts/check_sources.py sources.txt
```

Run report-structure validation:

```bash
python -X utf8 scripts/verify_report.py report.md
```

Run the security-boundary unit tests:

```bash
python -X utf8 -m unittest discover -s tests -v
```

After changing `SKILL.md`, `references/`, or `scripts/`, update the version number and the behavior descriptions in the README.

## Known Limitations

- Link probing confirms only the HTTP status. It does not prove that the body is readable or that the content is true.
- JavaScript-rendered pages, anti-bot pages, and rate-limited pages may return unreliable status information.
- Research quality depends on the search, source retrieval, and browser tools available to the platform.
- The skill does not bypass paywalls, authentication, CAPTCHAs, or access controls.
- It does not provide investment, medical, or legal advice.

## Contributing

Before submitting a change:

1. Do not weaken the security boundary for external content.
2. Do not remove user-authorization requirements from default workflows.
3. Add documentation and tests for changes to network, permission, or file access.
4. Update the version number and README.

## License

This repository does not currently declare an open-source license. All rights are reserved by default. Contact the repository owner for permission before reusing, modifying, or distributing the project.