# md2png-lite

纯 Python Markdown 渲染器示例。

## 能力

- 标题 / 段落
- 引用块
- 列表
- 表格
- 代码高亮
- 数学公式

> 这是一段引用。适合测试背景、边框和换行。

1. 第一项
2. 第二项
3. 第三项

| 项目 | 内容 |
| --- | --- |
| 渲染器 | Pillow |
| 解析器 | markdown-it-py |
| 代码高亮 | Pygments |

```python
def greet(name: str) -> str:
    return f"hello, {name}"

print(greet("hyw"))
```

行内公式：$E = mc^2$

块公式：

$$
\int_0^1 x^2 dx = \frac{1}{3}
$$
