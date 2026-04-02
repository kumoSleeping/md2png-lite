# 小样例 12：图片渲染

下面先看块级本地图片。它应该被居中摆放，并保留原始纵横比。

![本地示意卡片](examples/assets/sample_image_card.xpm)

这里再混排一个行内图片 ![行内卡片](examples/assets/sample_image_card.xpm) 和一个 data URI 小图标 ![data icon](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAAaElEQVR4nGP8+v7ZfwYqAiYGKgMWbILna9yJ0mzYshNDjBHZy8QahM9gJgYqAyZKXYeulz6RAgPe3I4M2MDWr/sZcAEmBioDplEDaRvLW/HEJv0jxRBLRh8UeZkRWwFLteKLGoDqXgYAtO8juNrqgtEAAAAASUVORK5CYII=)，看基线和行高是否自然。

最后故意放一个失效图片：![missing image fallback](examples/assets/not-found.png)

这里应该退化成 alt 文本，而不是把整段渲染炸掉。

- 看块级图片是否居中
- 看行内图片是否不顶乱文本
- 看 data URI 是否能被解码
- 看失败时是否回退为 alt 文本
