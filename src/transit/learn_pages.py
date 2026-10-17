"""
学习内容公开页面渲染

索引页与分类页由服务端渲染：有后端之后不必再让浏览器取 JSON 自己拼，
发布后的可用性自检也才拿得到含内容的 HTML。
"""

import html
from typing import Optional

# 分类色盘：按分类顺序取色
CATEGORY_COLORS = ["#35618F", "#2E7D6E", "#B0713A", "#6F5B93", "#A94F4F"]

PAGE_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%2316324A'/%3E%3Ccircle cx='8' cy='8' r='3.5' fill='%23F4F5F2'/%3E%3C/svg%3E">
<style>
:root {{ --paper:#F4F5F2; --card:#FFFFFF; --ink:#16324A; --body:#33383E;
  --line:#D8DCD6; }}
* {{ box-sizing:border-box; margin:0; }}
body {{ background:var(--paper); color:var(--body);
  font:16px/1.75 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }}
.wrap {{ max-width:1000px; margin:0 auto; padding:48px 24px 64px; }}
a {{ color:var(--ink); }}
.crumb {{ font:13px/1 ui-monospace,"SF Mono",Consolas,monospace; color:#8A9198;
  letter-spacing:.02em; }}
.crumb a {{ color:inherit; }}
h1 {{ font-family:"Noto Serif SC","Songti SC",SimSun,serif; font-weight:600;
  font-size:34px; color:var(--ink); margin:10px 0 4px; }}
h2 {{ font-family:"Noto Serif SC","Songti SC",SimSun,serif; font-weight:600;
  font-size:20px; color:var(--ink); margin:36px 0 12px; }}
.desc {{ color:#6A7178; margin-bottom:36px; }}
.topic {{ display:block; background:var(--card); border:1px solid var(--line);
  border-left:3px solid var(--accent); padding:16px 20px; margin-bottom:12px;
  text-decoration:none; }}
.topic .path {{ font:12px/1.4 ui-monospace,"SF Mono",Consolas,monospace; color:var(--accent); }}
.topic h3 {{ font-family:"Noto Serif SC","Songti SC",SimSun,serif; font-weight:600;
  font-size:19px; color:var(--ink); margin:4px 0 6px; }}
.topic .tdesc {{ font-size:13.5px; line-height:1.62; color:#6A7178; margin:0 0 8px; }}
.topic .meta {{ font:12px/1.4 ui-monospace,"SF Mono",Consolas,monospace; color:#8A9198; }}
.empty {{ color:#6A7178; }}
footer {{ margin-top:44px; font:12px/1.6 ui-monospace,"SF Mono",Consolas,monospace;
  color:#8A9198; }}
</style>
</head>
<body>
<div class="wrap">
{body}
  <footer>{footer}</footer>
</div>
</body>
</html>
"""


def _topic_card(topic: dict, accent: str, href_prefix: str = "") -> str:
    """
    渲染一张专题卡片，呈现标题与路径

    Args:
        topic: 专题条目
        accent: 该分类的强调色
        href_prefix: 相对链接前缀——索引页在 /learn/ 下需带分类段，分类页在 /learn/<category>/ 下不带
    """
    path = topic.get("path", "")
    slug = topic.get("slug", "")
    href = f"{href_prefix}{slug}/" if path.endswith("/") else f"{href_prefix}{slug}.html"
    tags = " ".join(f"#{html.escape(t)}" for t in topic.get("tags", []))
    desc = topic.get("desc", "")

    return (
        f'    <a class="topic" href="{href}" style="--accent:{accent}">\n'
        f'      <p class="path">{html.escape(path)}</p>\n'
        f'      <h3>{html.escape(topic.get("title", ""))}</h3>\n'
        + (f'      <p class="tdesc">{html.escape(desc)}</p>\n' if desc else "")
        + f'      <p class="meta">{html.escape(topic.get("date", ""))}'
        + (f" · {tags}" if tags else "")
        + "</p>\n    </a>"
    )


def _sorted_topics(category: dict) -> list[dict]:
    return sorted(category.get("topics", []), key=lambda t: t.get("date", ""), reverse=True)


def render_index_page(registry: dict) -> str:
    """渲染索引页：按分类列出已发布专题"""
    categories = registry.get("categories", [])

    if not categories:
        body = '  <h1>学习站</h1>\n  <p class="empty">暂无内容。</p>'
    else:
        blocks = ["  <h1>学习站</h1>", '  <p class="desc">按分类浏览已发布的学习专题。</p>']
        for i, category in enumerate(categories):
            accent = CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
            slug = category.get("slug", "")
            blocks.append(
                f'  <h2><a href="./{html.escape(slug)}/">{html.escape(category.get("name", slug))}</a></h2>'
            )
            topics = _sorted_topics(category)
            if topics:
                blocks.extend(_topic_card(t, accent, f"./{slug}/") for t in topics)
            else:
                blocks.append('  <p class="empty">该分类暂无内容。</p>')
        body = "\n".join(blocks)

    return PAGE_TMPL.format(title="学习站", body=body, footer="学习站 · 由 transit 托管")


def render_category_page(registry: dict, category_slug: str) -> Optional[str]:
    """渲染分类页：列出该分类下的已发布专题；分类不存在时返回 None"""
    categories = registry.get("categories", [])
    index = next((i for i, c in enumerate(categories) if c.get("slug") == category_slug), None)
    if index is None:
        return None

    category = categories[index]
    accent = CATEGORY_COLORS[index % len(CATEGORY_COLORS)]
    name = category.get("name", category_slug)

    blocks = [
        f'  <p class="crumb"><a href="../../learn/">学习站</a> / {html.escape(category_slug)}/</p>',
        f"  <h1>{html.escape(name)}</h1>",
    ]
    if category.get("description"):
        blocks.append(f'  <p class="desc">{html.escape(category["description"])}</p>')

    topics = _sorted_topics(category)
    if topics:
        blocks.extend(_topic_card(t, accent) for t in topics)
    else:
        blocks.append('  <p class="empty">该分类暂无内容。</p>')

    return PAGE_TMPL.format(
        title=f"{name} · 学习站",
        body="\n".join(blocks),
        footer="学习站 · 由 transit 托管",
    )
