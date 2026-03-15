# 小样例 04：表格与代码

| Region | 状态 | 指标 |
| --- | --- | --- |
| CN-East | 正常 | $P95 = 148ms$ |
| US-West | Healthy | ErrorRate = 0.21% |
| JP-Tokyo | 安定 | $QPS \approx 12.4k$ |

```python
def route_score(latency_ms: float, error_rate: float) -> float:
    alpha, beta = 0.8, 220.0
    return latency_ms * alpha + error_rate * beta
```

这里同时看几件事：

- 表格列宽是否自然
- 代码块里的英文字体是否稳定
- 同一页里中文、英文和公式有没有突兀换风格
