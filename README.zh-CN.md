<p align="center">
  <img src="docs/assets/alvenx-wordmark.svg" width="320" alt="AlvenX — Agent Reliability">
</p>

# Browser Agent Regression

[English](README.md) · [证据协议](docs/evidence-schema.md) · [v1 证据](docs/evidence/v1.0.0-calibration.json)

Browser Agent Regression 是一个本地优先的浏览器 Agent 回归工具，用来回答：**一次模型、
提示词、工具或框架变更，究竟提高了可靠性，还是悄悄破坏了原本能通过的工作流？**

v1 核心包含三个可重置任务、四种语义不变 UI 变体、独立检查点评分、重复的
baseline/candidate 比较、首个失败点定位和可验证 JSON 证据。默认 demo 使用内置确定性
driver；模型适配器可以把同一证据协议用于真实 Agent 实验。

## 快速开始

支持 Python 3.11–3.13。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium

browser-agent-regression doctor
browser-agent-regression demo
browser-agent-regression studio
```

`demo` 会运行 12 次受控尝试并写入 `runs/demo-report.json`。预期结果是 clean 行为保持一致，
并且人为设置的 popup-blind candidate 在三个任务上各产生一个能定位到首个检查点的回归。
报告会记录合成 harness 校准使用的 driver、任务和协议。

`studio` 会打开监听本机回环地址的可视化界面，遵循 AlvenX 官网产品设计语言。界面默认
读取已提交证据，并可通过液态玻璃按钮在内存中运行同一套确定性校准，同时保持已提交报告不变。详见
[Studio 使用说明](docs/studio.md)。

验证新报告或仓库内 v1 证据：

```powershell
browser-agent-regression verify --report runs\demo-report.json
browser-agent-regression verify --report docs\evidence\v1.0.0-calibration.json
```

## v1 稳定边界

- CLI：`demo`、`oracle`、`calibrate`、`verify`、`doctor`、`serve`、`studio` 和可选 `deepseek`。
- 固定的任务 ID、变体 ID 和有序检查点合同。
- 证据 schema `1.0`、协议 ID、fixture 哈希、环境、逐次结果、汇总、回归和首个失败点。
- 退出码：`0` 表示通过，`1` 表示实验完成但未满足验收，`2` 表示证据或运行环境错误。

验证器会从逐次结果重新计算汇总与回归、检查每个检查点合同、核对已安装 fixture 的
SHA-256，并拒绝凭据形态字段。历史 schema `0.2` 报告仍可验证。

## 内置实验

```powershell
# Reference driver 在所有任务和变体上的稳定性
browser-agent-regression oracle --runs 30 --output runs\oracle.json

# Reference 与 popup-blind candidate 的受控对照
browser-agent-regression calibrate --runs 10 --output runs\calibration.json
```

仓库内 v1 校准证据对每个 baseline/candidate/任务/变体单元重复三次。clean 页面保持一致；
popup overlay 下 candidate 的三个任务均从 100% 降至 0%，首个失败检查点的一致率均为 100%。
配套 oracle 报告覆盖全部四种变体，两份报告都由 CI 调用公开 `verify` 命令验收。

## 可选真实 Agent

Browser Use + DeepSeek 适配器把相同任务和独立 DOM 评分用于模型驱动的运行，可能产生付费
API 请求：

```powershell
python -m pip install -e ".[agent]"
browser-agent-regression deepseek `
  --task preferences.notifications.v1 `
  --runs 1 `
  --headed
```

运行前先阅读 [DeepSeek 安装与安全用 Key 指南](docs/deepseek.zh-CN.md)。凭据只从环境变量或
隐藏输入读取，不会写入证据。

## 项目状态

v1 表示 runner、CLI、Python 包和证据合同已经可以稳定供外部使用。当前工作聚焦安装体验、
证据可读性，以及具名 Agent 与模型的适配。受控工作流适合重复回归定位；需要更广任务覆盖时，
可与 WebArena、BrowserGym 或团队内部 eval 组合使用。

## 开发检查

```powershell
python -m ruff check .
python -m pytest
python scripts\check_repository.py
python -m build
```

Apache-2.0 许可证。Browser Agent Regression 是 [AlvenX](https://alvenx.com) 开源项目。
