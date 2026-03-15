# 压力样例 03：公式与混排弹幕

这一份专门压：

- 连续行内公式
- 多个块级公式
- 公式与自然语言、列表、引用、代码穿插
- 数学符号和普通段落交替出现

---

## 1. 行内公式风暴

在推荐系统里，常见的目标函数可能写成 $L = \sum_{i=1}^{n} \ell(\hat{y_i}, y_i)$，而当我们考虑正则项时，又会变成
$L' = L + \lambda \lVert w \rVert_2^2$。如果再引入约束，可能需要检查 $P(A \mid B)$、$\mathbb{E}[X]$、$\sigma^2 = \mathbb{E}[(X-\mu)^2]$、$\nabla_\theta J(\theta)$、$\arg\max_x f(x)$ 这些表达式在同一个段落里是否还能排得清楚。

## 2. 块级公式连续输出

$$
\hat{\theta} = \arg\min_{\theta} \sum_{i=1}^{n} \left(y_i - f_\theta(x_i)\right)^2
$$

$$
KL(P \parallel Q) = \sum_x P(x)\log\frac{P(x)}{Q(x)}
$$

$$
\operatorname{softmax}(z_i) = \frac{e^{z_i}}{\sum_{j=1}^{k} e^{z_j}}
$$

$$
\text{Attention}(Q,K,V) = \operatorname{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V
$$

$$
\forall \epsilon > 0,\ \exists N \in \mathbb{N},\ n > N \Rightarrow |a_n - L| < \epsilon
$$

---

## 3. 公式 + 列表

1. 稳定性指标
   - 可用性：$A = \frac{T_{up}}{T_{all}}$
   - 延迟预算：$B = \max(0, 220 - P95)$
   - 错误预算燃烧率：$R = \frac{e_{obs}}{e_{allow}}$
2. 成本指标
   - 单请求成本：$C_{req} = \frac{C_{infra}+C_{traffic}}{N_{request}}$
   - 单成功订单成本：$C_{order} = \frac{C_{total}}{N_{success}}$
3. 风险指标
   - 波动性近似：$\sigma \approx \sqrt{\frac{1}{n}\sum (x_i-\mu)^2}$
   - 超阈概率：$P(X > \tau)$

> 如果渲染器在这里出现公式尺寸不一致、垂直对齐偏移、或者段间距突兀，那几乎可以马上看出来。

---

## 4. 代码 + 数学说明

```python
def burn_rate(observed_error: float, allowed_error: float) -> float:
    if allowed_error <= 0:
        raise ValueError("allowed_error must be positive")
    return observed_error / allowed_error


def score(error_rate: float, latency_ms: float, queue_depth: float) -> float:
    alpha, beta, gamma = 1000.0, 0.7, 0.02
    return alpha * error_rate + beta * latency_ms + gamma * queue_depth
```

上面的 `score()` 实际上就是把下面这个经验公式编码化：

$$
Score = \alpha \cdot ErrorRate + \beta \cdot Latency + \gamma \cdot QueueDepth
$$

并且你可以在注释里继续塞入行内数学，例如当 $Score > 300$ 时进入人工复核，当 $Score > 500$ 时直接触发强制保护。

---

## 5. 长段落收尾

最后再给一段超长的数学叙述：在一个既需要考察稳定性又需要考察资源利用率的系统里，任何单一指标都不足以支撑最终决策。因此我们往往把多个信号投影到同一个评分空间里，再结合阈值、趋势和上下文解释做判断。换句话说，真正难渲染的不是某一条孤立公式，而是像这样把 $f(x)$、$\nabla f(x)$、$\sum$、$\int$、$\log$、$\frac{a}{b}$、$\sqrt{x}$ 这些公式片段夹在大段自然语言之中，并让整页依然保持清楚、均衡、可读。
