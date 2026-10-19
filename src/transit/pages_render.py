"""
页面托管的公开页面渲染

索引页与分类页由服务端渲染：有后端之后不必再让浏览器取 JSON 自己拼，
发布后的可用性自检也才拿得到含内容的 HTML。
"""

import html
from typing import Optional

# 分类色盘：按分类顺序取色
CATEGORY_COLORS = ["#35618F", "#2E7D6E", "#B0713A", "#6F5B93", "#A94F4F"]

SITE_TITLE = "页面站"

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
.entry {{ display:block; background:var(--card); border:1px solid var(--line);
  border-left:3px solid var(--accent); padding:16px 20px; margin-bottom:12px;
  text-decoration:none; }}
.entry .path {{ font:12px/1.4 ui-monospace,"SF Mono",Consolas,monospace; color:var(--accent); }}
.entry h3 {{ font-family:"Noto Serif SC","Songti SC",SimSun,serif; font-weight:600;
  font-size:19px; color:var(--ink); margin:4px 0 6px; }}
.entry .tdesc {{ font-size:13.5px; line-height:1.62; color:#6A7178; margin:0 0 8px; }}
.entry .meta {{ font:12px/1.4 ui-monospace,"SF Mono",Consolas,monospace; color:#8A9198; }}
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


def _entry_card(entry: dict, accent: str, href_prefix: str = "") -> str:
    """
    渲染一张页面卡片，呈现标题与路径

    Args:
        entry: 页面条目
        accent: 该分类的强调色
        href_prefix: 相对链接前缀——索引页在 /pages/ 下需带分类段，分类页在 /pages/<category>/ 下不带
    """
    path = entry.get("path", "")
    slug = entry.get("slug", "")
    href = f"{href_prefix}{slug}/"
    tags = " ".join(f"#{html.escape(t)}" for t in entry.get("tags", []))
    desc = entry.get("desc", "")

    return (
        f'    <a class="entry" href="{href}" style="--accent:{accent}">\n'
        f'      <p class="path">{html.escape(path)}</p>\n'
        f'      <h3>{html.escape(entry.get("title", ""))}</h3>\n'
        + (f'      <p class="tdesc">{html.escape(desc)}</p>\n' if desc else "")
        + f'      <p class="meta">{html.escape(entry.get("date", ""))}'
        + (f" · {tags}" if tags else "")
        + "</p>\n    </a>"
    )


def _sorted_pages(category: dict) -> list[dict]:
    return sorted(category.get("pages", []), key=lambda p: p.get("date", ""), reverse=True)


def render_index_page(registry: dict) -> str:
    """渲染索引页：按分类列出已发布页面"""
    categories = registry.get("categories", [])

    if not categories:
        body = f'  <h1>{SITE_TITLE}</h1>\n  <p class="empty">暂无页面。</p>'
    else:
        blocks = [
            f"  <h1>{SITE_TITLE}</h1>",
            '  <p class="desc">按分类浏览已托管的页面。</p>',
        ]
        for i, category in enumerate(categories):
            accent = CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
            slug = category.get("slug", "")
            blocks.append(
                f'  <h2><a href="./{html.escape(slug)}/">{html.escape(category.get("name", slug))}</a></h2>'
            )
            pages = _sorted_pages(category)
            if pages:
                blocks.extend(_entry_card(p, accent, f"./{slug}/") for p in pages)
            else:
                blocks.append('  <p class="empty">该分类暂无页面。</p>')
        body = "\n".join(blocks)

    return PAGE_TMPL.format(title=SITE_TITLE, body=body, footer=f"{SITE_TITLE} · 由 transit 托管")


def render_category_page(registry: dict, category_slug: str) -> Optional[str]:
    """渲染分类页：列出该分类下的已发布页面；分类不存在时返回 None"""
    categories = registry.get("categories", [])
    index = next((i for i, c in enumerate(categories) if c.get("slug") == category_slug), None)
    if index is None:
        return None

    category = categories[index]
    accent = CATEGORY_COLORS[index % len(CATEGORY_COLORS)]
    name = category.get("name", category_slug)

    blocks = [
        f'  <p class="crumb"><a href="../../pages/">{SITE_TITLE}</a> / {html.escape(category_slug)}/</p>',
        f"  <h1>{html.escape(name)}</h1>",
    ]
    if category.get("description"):
        blocks.append(f'  <p class="desc">{html.escape(category["description"])}</p>')

    pages = _sorted_pages(category)
    if pages:
        blocks.extend(_entry_card(p, accent) for p in pages)
    else:
        blocks.append('  <p class="empty">该分类暂无页面。</p>')

    return PAGE_TMPL.format(
        title=f"{name} · {SITE_TITLE}",
        body="\n".join(body for body in blocks),
        footer=f"{SITE_TITLE} · 由 transit 托管",
    )
