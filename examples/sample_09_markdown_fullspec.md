# 小样例 09：Markdown 全格式覆盖

这是一份偏“功能覆盖”的 Markdown 样例，目标不是好看，而是尽可能把常见元素放在一页内容里，方便快速回归。

---

## 1. 标题层级

### 三级标题

#### 四级标题

##### 五级标题

###### 六级标题

## 2. 行内样式

普通文本、**粗体**、*斜体*、~~删除线~~、`行内代码`、[链接文本](https://example.com) 应该能稳定混排。

中英文混排也要自然，比如 release `v2.4.1`、P95、API、QPS、SLO、latency budget。

第一行末尾保留两个空格触发换行。  
这一行应该是紧接着的换行结果。

## 3. 引用与列表

> 这是一段引用。
>
> 第二行引用继续测试段间距和边框。

- 无序列表第一项
- 无序列表第二项
- 无序列表第三项，带 **强调** 和 `inline code`

1. 有序列表第一项
2. 有序列表第二项
3. 有序列表第三项

## 4. 表格

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `env` | 环境名 | `staging` |
| `p95` | 95 分位延迟 | `148ms` |
| `status` | 当前状态 | `healthy` |

## 5. 代码块

```python
def render_score(error_rate: float, latency_ms: float) -> float:
    alpha, beta = 1000.0, 0.8
    return error_rate * alpha + latency_ms * beta
```

```bash
python3 scripts/render_examples.py --pattern 'sample_09_*.md'
```

## 6. 数学公式

行内公式：$E = mc^2$、$\frac{a+b}{c+d}$、$\sigma^2 = \mathbb{E}[(X-\mu)^2]$。

块级公式：

$$
\operatorname{softmax}(z_i) = \frac{e^{z_i}}{\sum_{j=1}^{k} e^{z_j}}
$$

## 7. 收尾段落

如果这一页渲染正确，通常意味着标题、正文、引用、列表、表格、代码和公式这几条主链路都没有明显退化。
