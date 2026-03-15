# 小样例 10：常见代码大合集

这一页专门测试“多数日常开发语言”的代码块表现。重点看字体、颜色、高亮边界和长行换行。

## Python

```python
from dataclasses import dataclass

@dataclass(slots=True)
class Task:
    name: str
    done: bool = False

def pending(tasks: list[Task]) -> list[str]:
    return [task.name for task in tasks if not task.done]
```

## JavaScript

```javascript
export async function fetchProfile(userId) {
  const response = await fetch(`/api/users/${userId}`);
  if (!response.ok) throw new Error("request failed");
  return response.json();
}
```

## TypeScript

```typescript
type RenderPayload = {
  ok: boolean;
  mimeType: string;
  base64: string;
};

function isValid(payload: RenderPayload): boolean {
  return payload.ok && payload.mimeType === "image/png";
}
```

## Bash

```bash
set -euo pipefail
uv build --wheel
python3 scripts/render_examples.py --pattern 'sample_10_*.md'
```

## JSON

```json
{
  "renderer": "md2png-lite",
  "theme": "paper",
  "width": 1600,
  "scale": 1.15,
  "ok": true
}
```

## YAML

```yaml
render:
  provider: md2png-lite
  theme: paper
  width: 1600
  scale: 1.15
```

## SQL

```sql
SELECT service, env, p95_ms, error_rate
FROM metrics_snapshot
WHERE env IN ('staging', 'prod')
ORDER BY p95_ms DESC;
```

## Go

```go
func Sum(values []int) int {
    total := 0
    for _, value := range values {
        total += value
    }
    return total
}
```

## Rust

```rust
fn retry_limit(error_rate: f64, latency_ms: f64) -> usize {
    if error_rate > 0.02 || latency_ms > 250.0 { 1 } else { 3 }
}
```

## HTML / CSS

```html
<section class="card">
  <h1>Status</h1>
  <p>All systems nominal.</p>
</section>
```

```css
.card {
  border-radius: 16px;
  padding: 24px;
  background: #fffaf2;
}
```

如果这页稳定，通常说明代码渲染链路已经能覆盖大部分常见场景。
