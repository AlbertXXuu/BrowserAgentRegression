# 使用 DeepSeek 运行 Browser Use

[English](deepseek.md)

这是可选的真实 Agent 路径：Browser Use 操作同一组本地 fixture，结束后由独立 DOM
检查点评分。任务和 Browser Use 提取的页面表示会发送到按量计费的 DeepSeek API。
确定性的 `oracle` 与 `calibrate` 仍完全离线，不需要 API Key。

## 1. 准备条件

- Python 3.11–3.13
- DeepSeek API Key，并确保账户余额充足
- 当前仓库代码

在 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys)创建或管理 Key；当前模型和接口
以[官方 API 文档](https://api-docs.deepseek.com/zh-cn/)为准。本项目默认使用
`deepseek-v4-flash`，也可以通过 `--model deepseek-v4-pro` 切换。

## 2. 安装可选 Agent 依赖

在仓库根目录运行：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,agent]"
python -m playwright install chromium
```

`[agent]` 被刻意隔离为可选依赖。只运行确定性校准的用户不必安装 Browser Use 或模型
Provider SDK。

## 3. 先做一次 Agent smoke test

不要把 Key 直接写在命令行里。运行：

```powershell
browser-agent-regression deepseek `
  --task preferences.notifications.v1 `
  --variant clean `
  --runs 1 `
  --headed `
  --output deepseek-smoke.json
```

如果当前环境没有 `DEEPSEEK_API_KEY`，CLI 会显示 Key 管理链接，并提示：

```text
DeepSeek API key (masked with *; not stored):
```

在 Windows 中粘贴 Key 后按 Enter，每个字符会显示为一个 `*`，因此可以确认粘贴已经生效，
但不会暴露 Key 内容；其他平台继续使用完全隐藏的输入。Key 只会直接传给 Provider 客户端，
不会写入报告、仓库、Shell 历史或 `.env` 文件。

只有独立 DOM 检查点全部通过时，命令才返回退出码 `0`；模型自己声称“已完成”不算成功。
一次 Agent attempt 可能因多步操作或重试而产生多次付费模型请求，运行前请检查账户余额。

仓库内的薄适配层使用 DeepSeek JSON Output 请求完整的 Browser Use `AgentOutput`，再通过框架
的 Pydantic schema 校验。它不会猜测或修复格式错误的动作参数。这样可以避开对深层嵌套
Agent 输出强制使用 function call，同时不改变 Browser Use 的动作执行逻辑。

## 4. 运行三任务 Gate C

单任务验证成功后，用一次命令运行三个 clean 任务：

```powershell
browser-agent-regression deepseek --runs 1 --output deepseek-gate-c.json
```

真实 Agent 默认只运行 `clean`，避免意外消耗额度。需要比较扰动条件时再显式添加：

```powershell
browser-agent-regression deepseek `
  --runs 3 `
  --variant clean `
  --variant popup-overlay `
  --output deepseek-repeated.json
```

上例会产生 18 次 Agent attempt：3 个任务 × 2 种条件 × 3 次重复；每次 attempt 都可能
包含多次付费 API 请求。CLI 会在开始前明确显示 Agent attempt 总数。

## 5. 环境变量与清理

CI 或其他非交互环境应通过平台的 Secret Store 提供 `DEEPSEEK_API_KEY`。缺少该变量时，
命令会拒绝在非交互环境中运行。

如果希望只在当前 PowerShell 进程中设置 Key，并在输入时隐藏字符：

```powershell
$secureKey = Read-Host "DeepSeek API key" -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
  $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
}
```

运行结束后清除当前进程变量：

```powershell
Remove-Item Env:DEEPSEEK_API_KEY
```

不要为短期测试使用 `setx`，不要提交 `.env`，也不要在 Issue 中附上 Key、Cookie 或未脱敏
的私有轨迹。

## 报告代表什么

真实 Agent 报告继续使用 evidence schema `0.2`，并标记
`evidence_kind: "real-agent"`。报告记录 Browser Use 版本、模型、无视觉配置、运行次数、
浏览器显示模式、fixture 哈希、耗时、检查点和受限长度的错误，但不会记录 API Key。这些
受控本地结果只证明集成可行性，不是 DeepSeek 或 Browser Use 的通用 benchmark。
