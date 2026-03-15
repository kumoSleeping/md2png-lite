# 小样例 03：块级公式对比

下面三条公式的结构复杂度差很多，适合快速看块级公式是否被缩得过小。

$$
Loss = \sum_{i=1}^{n} \left(y_i - \hat{y_i}\right)^2
$$

$$
\operatorname{softmax}(z_i) = \frac{e^{z_i}}{\sum_{j=1}^{k} e^{z_j}}
$$

$$
\forall \epsilon > 0,\ \exists N \in \mathbb{N},\ n > N \Rightarrow |a_n - L| < \epsilon
$$

如果这三条里第一条明显比第二条和第三条“像缩小了一圈”，就能很快察觉出来。
