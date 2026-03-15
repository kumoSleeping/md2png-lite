# 小样例 11：长文混合公式文章

这是一篇偏学术说明风格的长文，专门测试“自然语言 + 高频公式”的混排表现。重点不是孤立公式，而是大量公式碎片夹在连续段落里时，页面是否仍然耐读。

## 背景

在一个需要同时考虑准确率、稳定性和成本的系统里，我们常常会把多个信号压缩到同一个决策函数中。例如，最终评分可以写成
$Score = \alpha \cdot ErrorRate + \beta \cdot Latency + \gamma \cdot QueueDepth$，其中 $\alpha, \beta, \gamma > 0$，并且通常满足 $\alpha \gg \beta > \gamma$。

如果只观察单一指标，比如 $P95$ 或 $P99$，系统就可能在另外一个维度上持续退化。因此更常见的做法是把 $\mu$、$\sigma^2$、$\Delta trend$、$BurnRate$ 等变量一起纳入评估。

## 目标函数

我们先定义一个更完整的经验目标：

$$
J(\theta) = \sum_{i=1}^{n} \ell(\hat{y_i}, y_i) + \lambda \lVert \theta \rVert_2^2
$$

如果系统还要满足资源约束，那么又可以进一步写成

$$
\hat{\theta} = \arg\min_{\theta} J(\theta) \quad \text{s.t.} \quad C(\theta) \le B
$$

这里的 $C(\theta)$ 可以理解为成本函数，$B$ 表示预算上界。

## 概率解释

从概率视角看，一个请求触发降级的条件可以写成 $P(X > \tau) > \delta$。如果延迟分布满足近似高斯假设，那么
$\sigma^2 = \mathbb{E}[(X-\mu)^2]$ 可以作为波动性度量，而标准分数
$z = \frac{x-\mu}{\sigma}$ 又能帮助我们快速判断当前点是否偏离常态。

更进一步，如果系统引入贝叶斯更新，那么后验分布满足

$$
P(\theta \mid D) = \frac{P(D \mid \theta) P(\theta)}{P(D)}
$$

这类公式单独看不难，真正难的是当它们不断穿插在整篇文章里时，字号、基线和段距还能不能保持稳定。

## 工程化落地

在工程实现中，我们往往不会直接把复杂公式原样丢给执行系统，而是先落成更容易维护的代码表达。例如：

```python
def score(error_rate: float, latency_ms: float, queue_depth: float) -> float:
    alpha, beta, gamma = 1000.0, 0.7, 0.02
    return alpha * error_rate + beta * latency_ms + gamma * queue_depth
```

它对应的其实就是上面的线性组合形式，而当 $Score > 300$ 时进入人工复核、当 $Score > 500$ 时触发保护，这种规则又可以写成分段函数：

$$
Action(Score)=
\begin{cases}
Observe, & Score \le 300 \\
Review, & 300 < Score \le 500 \\
Protect, & Score > 500
\end{cases}
$$

## 进一步分析

如果要分析系统长期趋势，就会遇到求和、积分和极限混排的场景。例如累计损失可以写成
$L_T = \sum_{t=1}^{T} \ell_t$，连续情况下又近似为
$L = \int_0^T f(t)\,dt$。收敛性分析时常出现
$\forall \epsilon > 0,\ \exists N \in \mathbb{N},\ n > N \Rightarrow |a_n - L| < \epsilon$ 这样的表达式。

而在机器学习场景里，softmax、attention 和正则项又会进一步把视觉复杂度抬高：

$$
\operatorname{softmax}(z_i) = \frac{e^{z_i}}{\sum_{j=1}^{k} e^{z_j}}
$$

$$
\operatorname{Attention}(Q,K,V) = \operatorname{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V
$$

## 总结

如果这一页最终看起来仍然“像一篇正常文章”，而不是一堆拼接出来的公式截图，就说明渲染器已经开始具备真实长文场景下的可读性。真正好的效果不是某一条公式特别漂亮，而是整篇文章从头到尾都稳。
