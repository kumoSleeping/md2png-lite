# 压力样例 01：运营情报总图谱

这是一份刻意堆满元素的 Markdown，用来压渲染器的**段落换行**、**中英混排**、**多层列表**、**引用块**、**代码高亮**、**表格**和**公式**。  
如果这一份能稳定出图，基本能说明基础排版链路已经比较完整。

---

## 1. 背景叙述

在一次持续 72 小时的应急响应演练中，团队需要同时处理：

1. 多地域流量回切
2. 数据一致性校验
3. CDN 配置发布
4. 运维审计回放
5. 面向产品、客服、市场、法务的同步通报

> 这类文档的难点不在“某一种 Markdown 语法”，而在同一页里把各种模块混在一起。  
> 渲染器如果只有轻量文本能力，就会在这里开始显得局促。

### 1.1 现象概览

- 中文段落里混入 `inline code`、URL、英文实体名，例如 `user-profile-service`、`edge-worker`、`retry budget`
- 英文段落里再混入中文注释，比如 *the effective failover window should remain below 90 seconds*，否则会引发“感知性抖动”
- 很长的连续片段，例如：
  `fallback_cluster.ap-southeast-1.internal.routing.policy.v20260313.canary-weighted`
- 多段连续强调：**高优先级**、*低风险*、~~废弃方案~~、[外部检查单](https://example.com/checklist)

### 1.2 嵌套列表

1. 一级任务 A
   - 二级观察点 A-1：业务错误率上升时优先判断是否为缓存穿透，而不是立刻归因为数据库慢查询
   - 二级观察点 A-2：如果是跨地域切流，先看边缘节点 `5xx`，再看源站 `4xx/5xx`
   - 二级观察点 A-3：
     1. 先确认告警误报率
     2. 再检查自动扩容的触发阈值
     3. 最后记录每个窗口的恢复时间
2. 一级任务 B
   - 二级观察点 B-1
     - 三级说明 B-1-a：短时间抖动不一定是系统性故障
     - 三级说明 B-1-b：但如果 5 分钟内出现 3 次以上同方向尖峰，就应升级
     - 三级说明 B-1-c：把 `rate(error_total[1m]) / rate(request_total[1m])` 与 CPU、GC、下游超时同时看
3. 一级任务 C
   - 二级观察点 C-1：同步对外沟通口径
   - 二级观察点 C-2：明确“已经恢复”和“仍在观察”的边界

---

## 2. 代码与配置

```python
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass
class RegionSample:
    region: str
    latency_ms: list[float]
    error_rate: float


def choose_failover_target(samples: list[RegionSample]) -> str:
    healthy = [
        item
        for item in samples
        if item.error_rate < 0.015 and mean(item.latency_ms) < 180
    ]
    if not healthy:
        raise RuntimeError("no healthy region")
    healthy.sort(key=lambda item: (item.error_rate, mean(item.latency_ms), item.region))
    return healthy[0].region


if __name__ == "__main__":
    region = choose_failover_target(
        [
            RegionSample("ap-northeast-1", [123.2, 130.5, 118.9], 0.004),
            RegionSample("ap-southeast-1", [96.3, 99.1, 102.8], 0.012),
            RegionSample("us-west-2", [181.0, 176.4, 184.2], 0.003),
        ]
    )
    print("selected:", region)
```

```yaml
service: edge-router
version: 2026.03.13
strategy:
  mode: weighted-failover
  primary:
    region: ap-southeast-1
    weight: 84
  secondary:
    region: ap-northeast-1
    weight: 16
guards:
  max_error_rate: 0.02
  max_p95_latency_ms: 220
  cooldown_seconds: 180
```

```sql
WITH latest_window AS (
  SELECT
    region,
    service,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency,
    avg(error_rate) AS avg_error_rate,
    max(sample_time) AS latest_ts
  FROM traffic_health_snapshot
  WHERE sample_time >= now() - interval '15 minute'
  GROUP BY region, service
)
SELECT *
FROM latest_window
WHERE service = 'edge-router'
ORDER BY avg_error_rate ASC, p95_latency ASC;
```

---

## 3. 表格压力

| 维度 | 主站 | 备站 | 目标阈值 | 备注 |
| --- | --- | --- | --- | --- |
| 错误率 | 1.82% | 0.41% | `< 2.00%` | 主站仍可服务，但继续升高就要强切 |
| P95 延迟 | 238ms | 141ms | `< 220ms` | 主站超过阈值，备站正常 |
| 队列积压 | 19,320 | 2,114 | `< 5,000` | 主站消费能力抖动明显 |
| 缓存命中率 | 81.2% | 93.7% | `> 90%` | 主站热 key 分布异常 |
| 观测结论 | 需要限流 | 可以承接 | - | 建议先小流量切换验证 |

| 阶段 | 时间窗 | 操作 | 观察指标 | 决策 |
| --- | --- | --- | --- | --- |
| Phase 0 | T+00 ~ T+05 | 只读观测 | `error_rate`, `cpu`, `queue_depth` | 不动作 |
| Phase 1 | T+05 ~ T+10 | 5% 金丝雀 | `edge_5xx`, `origin_timeout`, `p95` | 若稳定继续 |
| Phase 2 | T+10 ~ T+20 | 25% 扩大 | `checkout_success`, `login_success`, `cdn_hit` | 若异常回滚 |
| Phase 3 | T+20 ~ T+30 | 50% 承接 | `settlement_delay`, `write_lag` | 保留人工开关 |
| Phase 4 | T+30 ~ T+45 | 100% 切换 | `global_error_budget_burn` | 完成主站摘流 |

---

## 4. 公式区

行内公式示例：$SLO = 1 - \frac{error\_requests}{total\_requests}$  
另一个行内公式：$\hat{\mu} = \frac{1}{n}\sum_{i=1}^n x_i$

块公式一：

$$
Availability = \frac{T_{total} - T_{downtime}}{T_{total}}
$$

块公式二：

$$
RiskScore = \alpha \cdot ErrorRate + \beta \cdot P95Latency + \gamma \cdot QueueDepth
$$

块公式三：

$$
\operatorname{burn\_rate}(t) = \frac{observed\_error(t)}{allowed\_error(t)}
$$

---

## 5. 连续段落

这是一大段连续文本，用来测试自动换行、不同字符宽度、长句中插入英文短语、以及行内强调的组合表现。系统在进入高压阶段后，如果渲染器不能正确处理“中文 + English phrase + `inline code` + 数学符号 $\lambda$ + 长链接描述”这种混排，就很容易在视觉上出现松散、断裂或者过度压缩的问题。因此这里故意把所有元素放在同一段里，并且让句子长度明显超过一屏正常宽度，以验证布局算法在不依赖浏览器的情况下仍然可以保持相对稳定、清晰、可读。

在第二段里，我们继续增加密度：运维人员需要在 10 分钟内完成主备切流、缓存预热、日志样本对比、告警降噪和审计回填。如果在这个窗口内产生了多个异步任务并行更新，比如 `sync-audit-indexer`、`rewrite-edge-cookies`、`warmup-route-cache`、`verify-payment-idempotency`，渲染器需要仍然能让读者快速定位到关键词，而不是让整段看起来像一整块“发灰”的字符墙。

> 最后再加一层引用，里面继续塞长段落。  
> 当引用块内部也出现长句、链接、行内代码和数学表达式，例如 `latency_budget = 220ms` 与 $P(X > 220)$ 同时出现时，布局会更容易暴露 bug。
