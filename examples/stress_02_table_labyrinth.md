# 压力样例 02：表格与代码迷宫

这一份专门压：

- 超多表格
- 表格单元格里混合 `inline code`、强调、链接
- 多语言代码块
- 长行折叠

---

## 1. 多表格矩阵

| 模块 | 接口 | QPS | P95 | 错误率 | 状态 |
| --- | --- | ---: | ---: | ---: | --- |
| 用户中心 | `/api/v2/profile/query` | 12,430 | 87ms | 0.14% | 正常 |
| 用户中心 | `/api/v2/profile/update` | 4,112 | 129ms | 0.31% | 正常 |
| 订单中心 | `/api/v3/order/create` | 8,523 | 192ms | 0.92% | 观察 |
| 订单中心 | `/api/v3/order/refund` | 1,244 | 233ms | 1.83% | 升级 |
| 结算中心 | `/internal/settlement/replay` | 422 | 341ms | 2.11% | 风险 |
| 风控网关 | `/risk/evaluate/decision-tree` | 2,883 | 118ms | 0.21% | 正常 |

| 指标 | 周一 | 周二 | 周三 | 周四 | 周五 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| 注册转化率 | 12.1% | 12.4% | 12.8% | 11.9% | 12.2% | 轻微波动 |
| 下单成功率 | 94.3% | 94.1% | 93.8% | 90.4% | 92.6% | 周四异常 |
| 支付完成率 | 90.2% | 89.9% | 90.5% | 86.1% | 88.7% | 需排查 |
| 退款完成率 | 98.7% | 98.5% | 98.9% | 97.8% | 98.0% | 可接受 |
| 工单触达时长 | 4m | 4m | 5m | 11m | 7m | 明显恶化 |

| 环境 | 区域 | 副本数 | 配额 | 配置片段 | 备注 |
| --- | --- | ---: | --- | --- | --- |
| prod-a | ap-southeast-1 | 48 | `16C/32G` | `retry.max=2; timeout=1800ms; breaker.open=25s` | 线上主流量 |
| prod-b | ap-northeast-1 | 32 | `16C/32G` | `retry.max=3; timeout=2200ms; breaker.open=30s` | 灾备 |
| staging | ap-southeast-1 | 12 | `8C/16G` | `retry.max=1; timeout=1500ms; breaker.open=8s` | 压测环境 |

---

## 2. 单元格里带强调和代码

| 检查项 | 规则 | 风险说明 |
| --- | --- | --- |
| 幂等键 | 必须带 `x-idempotency-key` | 如果没有这个 header，重复提交下会放大并发写问题 |
| 缓存淘汰 | 优先 LRU，其次 TTL | 若 `cache.hit_ratio < 0.88`，通常意味着热点分布变了 |
| 限流 | 默认漏桶 | **不要** 在未确认真实峰值前贸然改成令牌桶 |
| 审计日志 | 全链路带 `trace_id` | [审计规范](https://example.com/audit) 要求字段完整，缺失会影响回放 |

---

## 3. 长代码块

```typescript
type HealthSnapshot = {
  region: string
  service: string
  p95: number
  errorRate: number
  queueDepth: number
  cpu: number
  memory: number
}

function decide(snapshot: HealthSnapshot[]): string[] {
  return snapshot
    .filter(item => item.errorRate > 0.01 || item.p95 > 220 || item.queueDepth > 5000)
    .sort((a, b) => {
      const scoreA = a.errorRate * 1000 + a.p95 * 0.8 + a.queueDepth * 0.03 + a.cpu * 0.5
      const scoreB = b.errorRate * 1000 + b.p95 * 0.8 + b.queueDepth * 0.03 + b.cpu * 0.5
      return scoreB - scoreA
    })
    .map(item => `${item.region}/${item.service}`)
}
```

```bash
set -euo pipefail

kubectl get pods -A \
  -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,CPU_REQ:.spec.containers[*].resources.requests.cpu,MEM_REQ:.spec.containers[*].resources.requests.memory,NODE:.spec.nodeName' \
  | sed 's/<none>/NA/g' \
  | sort
```

```json
{
  "rollout": {
    "id": "2026-03-13-edge-router-prod",
    "stages": [
      {"name": "phase-0", "trafficPercent": 0, "durationSec": 300},
      {"name": "phase-1", "trafficPercent": 5, "durationSec": 300},
      {"name": "phase-2", "trafficPercent": 25, "durationSec": 600},
      {"name": "phase-3", "trafficPercent": 50, "durationSec": 900},
      {"name": "phase-4", "trafficPercent": 100, "durationSec": 0}
    ],
    "abortWhen": [
      "edge_5xx_rate > 0.02",
      "origin_timeout_rate > 0.01",
      "checkout_success_rate < 0.95",
      "payment_callback_delay_p95 > 10s"
    ]
  }
}
```

---

## 4. 极长段落 + 表格混排

如果一份文档里既有非常规则的表格，又有非常不规则的长段落，那么最容易暴露的问题通常是垂直节奏不稳：表格之后如果间距过紧，会显得拥挤；如果间距过松，又会让页面显得松散。此外，当代码块前后都带有说明段落时，读者会下意识把它当成一个整体模块来看，这时候边框、背景、内边距和行高就必须足够统一，否则整个页面会像是由多个独立截图硬拼出来的一样。

| 序号 | 描述 |
| --- | --- |
| A | 这是一个很长很长的单元格内容，用来观察多行折行时边距是否稳定、文本是否会贴边、以及不同宽度字符混排时的行高是否被正确计算。 |
| B | 这里再加上一些 `inline code`、**粗体强调**、*斜体说明* 和 [链接文字](https://example.com/details)，看它们在单元格中的处理是否还能保持一致。 |
