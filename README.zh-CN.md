<p align="center">
  <img src="docs/assets/ailumetra-wordmark.svg" width="320" alt="Ailumetra — Agent Reliability">
</p>

# Browser Agent Regression

**Browser Agent Regression 是 Ailumetra 系列中的开源浏览器 Agent 可靠性项目。**

[![CI](https://github.com/AlbertXXuu/BrowserAgentRegression/actions/workflows/ci.yml/badge.svg)](https://github.com/AlbertXXuu/BrowserAgentRegression/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

[English](README.md)

这是一个 local-first 实验，用来回答一个实际问题：**浏览器 Agent 更新后是真的更可靠了，
还是悄悄破坏了原本能够完成的工作流？**

项目目前处于 **5–7 天 Phase 0 验证期**，还不是通用框架。第一个可运行切片包含确定性
结账任务、语义不变的受控 UI 扰动、检查点级评分、重复运行和 JSON 回归报告。

> 当前完成了三个必需任务中的一个。只有 [PROJECT.md](PROJECT.md) 中所有技术和用户验证
> Gate 均通过，Phase 0 才是 **GO**。在此之前，这个仓库代表的是一个可证伪的项目假设，
> 不是已经完成的产品。

仓库通过 [AOS-0.1 符合性记录](docs/ailumetra-conformance.md)跟踪系列标准，但不会因此
扩大 Phase 0 范围。

## Phase 0 校准证据

第一个切片在本地同一份源码快照上重复运行。确定性 reference Oracle 在所有当前条件下均
完成 30/30 次：

| 条件 | Reference Oracle | 校准 Baseline | 校准 Candidate |
|---|---:|---:|---:|
| `clean` | 30/30 | 10/10 | 10/10 |
| `popup-overlay` | 30/30 | 10/10 | **0/10** |
| `delayed-render` | 30/30 | — | — |
| `layout-shift` | 30/30 | — | — |

人为设置的 popup-blind candidate 保持了 clean 条件下的成功率，但在 overlay 条件下下降
100 个百分点；十次失败均首先定位到 `checkout.email.accepted`。可以直接检查保存的
[Oracle 证据](docs/evidence/phase0-slice-01-oracle.json)与
[校准证据](docs/evidence/phase0-slice-01-calibration.json)。

这些是**合成 runner 校准结果**，不是模型或真实浏览器 Agent 的 benchmark 分数。它们只用来
证明 fixture 稳定且 runner 能检测回归，然后才值得接入真实 Agent。

## 为什么做这个项目

浏览器 Agent Demo 通常只能说明任务曾经成功一次。升级决策需要更强的证据：相同任务、
重复运行、受控变化、明确检查点，以及 baseline 与 candidate 的成对比较。

这个仓库会先验证这种更小的开发者工作流是否有用，再决定是否投入构建正式工具。

## 当前可运行切片

内置结账任务包含四种条件：

- `clean`
- `popup-overlay`
- `delayed-render`
- `layout-shift`

所有条件都保持任务语义不变。reference driver 是确定性 Oracle；人为降级的
popup-blind driver 用来证明 runner 能区分真实回归与 fixture 不稳定。两者都不是 AI
Agent benchmark 结果。

## 快速开始

支持 Python 3.11–3.13。

```bash
python -m venv .venv
```

在 PowerShell 中运行 `.venv\Scripts\Activate.ps1`，或在 macOS/Linux 中运行
`source .venv/bin/activate` 激活环境，然后安装项目与浏览器：

```bash
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

验证 fixture 与 Oracle 的稳定性：

```bash
browser-agent-regression oracle --runs 30
```

运行合成回归校准实验：

```bash
browser-agent-regression calibrate --runs 10 --output calibration.json
```

手动打开本地 fixture：

```bash
browser-agent-regression serve
```

## 帮助验证 Phase 0

如果你正在维护、评估或学习浏览器 Agent，请在自己的电脑上 clone 仓库并运行上面的两个
命令，然后提交
[Phase 0 独立运行反馈](https://github.com/AlbertXXuu/BrowserAgentRegression/issues/new?template=phase0-run.yml)。

成功和受阻的报告都有价值。只有非维护者提供了测试 revision、环境、命令、安全证据和具体
工作流反馈，才计入外部需求 Gate；Star 和页面浏览量不计入。

## 开发检查

```bash
python -m ruff check .
python -m pytest
```

## 许可证

Apache-2.0。

---

Ailumetra 开源项目。功能项目名独立于系列品牌。
