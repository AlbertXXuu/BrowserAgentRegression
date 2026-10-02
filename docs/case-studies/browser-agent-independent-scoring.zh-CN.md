# 浏览器生命周期误判与独立结果评分

2026-10-02 · BrowserAgentRegression

[English](browser-agent-independent-scoring.md) · [网站阅读版](https://alvenx.com/notes/engineering/browser-agent-independent-scoring-zh)

一次已经完成的设置任务，因为浏览器在评分前关闭而被记录为失败。修复保留了独立 DOM 检查所需的页面；另一次结账运行则说明，Agent 自己报告的成功或失败不能决定实验结果。

## 已完成的任务被记为失败

BrowserAgentRegression 在可重置的本地页面上评估明确的任务结果。设置任务要求 Agent 关闭产品更新通知、保留安全提醒并保存。三个检查点让任务是否完成可以直接观察，即使模型对自己操作的描述并不确定。

2026 年 8 月 15 日，第二次经过身份验证的 Browser Use 与 deepseek-v4-flash 冒烟运行已经达到这些可见结果，JSON 却记录为 0/1，所有检查点均为 false。保留的报告注明源代码修订 e5b812c，并将其归类为 runner 假阴性。如果直接把这个数字当成模型表现，就会把基础设施缺陷误归到 Agent 身上。

[保留的生命周期失败与源码修订](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-02.md)

## 让页面保留到评分结束

问题来自浏览器会话的生命周期。Browser Use 0.13.7 在 Agent.run() 返回前调用 Agent.close()；keep_alive=False 使这个关闭动作销毁共享会话，适配器随后无法读取 DOM。模型历史中一个临时的 AgentOutput 校验错误还掩盖了后续评分错误。

工程选择是保留评分器的观察窗口，并同时保存两类错误。任务合同仍由实际页面状态判定完成，轨迹错误作为诊断证据保留。基础设施失败必须先查明，实验才有条件支持性能结论。

[生命周期诊断记录](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-02.md)

## 先评分 DOM 再强制清理

当前 browser_use_deepseek.py 用 keep_alive=True 创建浏览器，等待 Agent 运行结束后，对同一页面调用 _score_page。finally 中始终尝试 browser.kill()。评分失败时，_scoring_failure_message 将评分器错误与 Agent 历史一起记录，并清除 API Key。

评分器检查具体选择器和值。结账任务要求邮箱正确、配送方式为 Express，并且状态提示可见且文本精确等于 Order confirmed。这些受控任务禁用模型 judge 与视觉输入，让结果检查独立于模型看到的页面表示和最后给出的叙述。

[当前适配器与确定性检查点脚本](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/src/browser_agent_regression/browser_use_deepseek.py)

## 另一次分歧验证评分边界

报告中的本地生命周期检查确认：Browser Use 关闭事件总线后，页面仍可评分，随后也能完成强制清理。源代码修订 2e41fa3 下的一次独立在线结账运行，进一步验证了修正后的评分边界和 JSON Output 兼容性。

结账 DOM 的三个检查点全部通过，Agent 却重复提交、产生空动作或格式错误动作，运行到第 12 步后以 success=false 结束。独立结果是 1/1。这与前面的生命周期缺陷有不同原因：评分器观察到了要求的结果，Agent 的页面表示却没有让模型确信确认信息已经可见。

之后 b817b68 下修正的 Gate C 运行一次通过三个任务、九个检查点，证明了记录条件下的适配器可行性；轨迹中保留的格式错误输出，仍然是评估执行可靠性时需要考虑的证据。

| 证据 | 独立结果 | 解释 |
| --- | --- | --- |
| e5b812c 设置冒烟运行 | 记录为 0/1 | 生命周期失败导致性能结果无效 |
| 2e41fa3 结账冒烟运行 | 1/1 | DOM 通过但 Agent 自报失败 |
| b817b68 修正后的 Gate C | 3/3 任务 | 单次运行证明集成可行性 |

[结账结果分歧](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-04.md) · [修正后的三任务可行性运行](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-gate-c-02.md)

## 这个案例能支持什么结论

这个案例展示了可观察的评分边界与具体的 harness 修复。单次冒烟运行不能估计模型的重复可靠性，第一个失败检查点本身也无法确定模型内部原因。历史误判及其排除理由继续保留。

BrowserGym 提供了覆盖更广的 Web 任务评估框架，可作为分离环境观察与 Agent 动作的设计参考。本文中的测量结果来自本仓库的 fixture、修订和报告。这个案例的实际启示是：评估器的生命周期也应进入实验合同。

[BrowserGym 一手仓库](https://github.com/ServiceNow/BrowserGym)

## 原始证据

- [原始假阴性](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-02.md)
- [独立通过与 Agent 判断分歧](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-04.md)
- [适配器实现](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/src/browser_agent_regression/browser_use_deepseek.py)
- [Gate C 证据](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-gate-c-02.md)
