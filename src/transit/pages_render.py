"""
页面托管的公开页面渲染

索引页与分类页由服务端渲染：有后端之后不必再让浏览器取 JSON 自己拼，
发布后的可用性自检也才拿得到含内容的 HTML。

视觉方向：把内容当作一个「技术学习档案柜」来编排，而不是卡片流。
索引页是一张按分类分段的宽表格——每行一条，日期、标题、摘要、分类标记
并列，读者一眼扫完整座书库的分量，再点进感兴趣的一条。
分类栏（桌面端）常驻在左侧，作为目录索引；窄屏收成横向滚动条。
"""

import html
from typing import Optional

SITE_TITLE = "学习档案"

# 分类色义：按分类顺序取色，同时用于左侧索引条与行首色标
CATEGORY_COLORS = ["#1F6F64", "#8A5A2B", "#4A5D7E", "#7A4A6B", "#5E6B3A"]


PAGE_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='2' fill='%23121B22'/%3E%3Crect x='4' y='3' width='8' height='1.6' fill='%23F2F4F3'/%3E%3Crect x='4' y='7.2' width='8' height='1.6' fill='%23F2F4F3'/%3E%3Crect x='4' y='11.4' width='5' height='1.6' fill='%231F6F64'/%3E%3C/svg%3E">
<style>
:root {{
  --paper:#F2F4F3; --card:#FFFFFF; --ink:#121B22; --body:#333B40;
  --muted:#6E777D; --rule:#CBD2D0; --accent:#1F6F64; --stamp:#8A5A2B;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
html {{ -webkit-text-size-adjust:100%; }}
body {{ background:var(--paper); color:var(--body);
  font:15px/1.65 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }}
a {{ color:inherit; }}
:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}

.shell {{ max-width:1440px; margin:0 auto; padding:clamp(20px,3vw,40px) clamp(16px,3vw,40px) 64px; }}

/* 顶部：档案柜铭牌 + 全站定位 */
.cabinet {{ display:flex; align-items:flex-end; justify-content:space-between;
  gap:16px; border-bottom:2px solid var(--ink); padding-bottom:12px; }}
.cabinet .name {{ font:600 26px/1.1 "Noto Serif SC","Songti SC",SimSun,serif;
  color:var(--ink); letter-spacing:.02em; }}
.cabinet .name small {{ display:block; font:11px/1.5 ui-monospace,"SF Mono",Consolas,monospace;
  color:var(--muted); letter-spacing:.14em; text-transform:uppercase; margin-top:4px; }}
.cabinet .cue {{ font:12px/1.5 ui-monospace,"SF Mono",Consolas,monospace;
  color:var(--muted); text-align:right; white-space:nowrap; }}

/* 主体：左侧目录 + 右侧记录表 */
.grid {{ display:grid; grid-template-columns:200px minmax(0,1fr); gap:clamp(20px,3vw,44px);
  margin-top:26px; align-items:start; }}

.rail {{ position:sticky; top:12px; }}
.rail .label {{ font:11px/1.5 ui-monospace,"SF Mono",Consolas,monospace; color:var(--muted);
  letter-spacing:.14em; text-transform:uppercase; padding-bottom:8px;
  border-bottom:1px solid var(--rule); }}
.rail a {{ display:flex; align-items:baseline; gap:8px; padding:9px 0 9px 10px;
  text-decoration:none; color:var(--ink); border-bottom:1px solid var(--rule);
  border-left:3px solid transparent; }}
.rail a:hover {{ color:var(--accent); }}
.rail a.active {{ border-left-color:var(--accent); font-weight:600; }}
.rail .count {{ margin-left:auto; font:11px/1 ui-monospace,"SF Mono",Consolas,monospace;
  color:var(--muted); }}
.rail .stat {{ margin-top:16px; font:11px/1.6 ui-monospace,"SF Mono",Consolas,monospace;
  color:var(--muted); }}

/* 分类段：细线 + 索引签，不用卡片 */
.section {{ margin-bottom:34px; }}
.section h2 {{ display:flex; align-items:baseline; gap:10px; font:600 17px/1.3
  "Noto Serif SC","Songti SC",SimSun,serif; color:var(--ink); padding-bottom:7px;
  border-bottom:1px solid var(--rule); margin-bottom:2px; }}
.section h2 .mark {{ width:9px; height:9px; border-radius:1px; background:var(--accent);
  align-self:center; flex:none; }}
.section h2 .n {{ margin-left:auto; font:11px/1 ui-monospace,"SF Mono",Consolas,monospace;
  color:var(--muted); letter-spacing:.04em; }}

/* 记录行：日期 | 标题与摘要 | 标签 */
.rec {{ display:grid; grid-template-columns:74px minmax(0,1fr) auto; gap:16px;
  align-items:baseline; padding:11px 6px; border-bottom:1px solid #E1E6E4;
  text-decoration:none; }}
.rec:hover {{ background:var(--card); }}
.rec .date {{ font:11px/1.5 ui-monospace,"SF Mono",Consolas,monospace; color:var(--stamp);
  letter-spacing:.02em; }}
.rec .title {{ font-size:15.5px; font-weight:600; color:var(--ink); line-height:1.45; }}
.rec:hover .title {{ color:var(--accent); }}
.rec .gist {{ display:block; font-size:13px; font-weight:400; color:var(--muted);
  line-height:1.55; margin-top:2px; }}
.rec .tags {{ display:flex; flex-wrap:wrap; gap:5px; justify-content:flex-end; max-width:220px; }}
.rec .tag {{ font:11px/1.5 ui-monospace,"SF Mono",Consolas,monospace; color:var(--muted);
  border:1px solid var(--rule); padding:0 6px; }}

/* 分类页：所在分类作为页眉 */
.hero {{ border-bottom:2px solid var(--ink); padding-bottom:14px; }}
.hero .crumb {{ font:11px/1.5 ui-monospace,"SF Mono",Consolas,monospace; color:var(--muted);
  letter-spacing:.06em; }}
.hero .crumb a {{ color:var(--accent); text-decoration:none; }}
.hero h1 {{ font:600 clamp(24px,3vw,32px)/1.2 "Noto Serif SC","Songti SC",SimSun,serif;
  color:var(--ink); margin-top:6px; }}
.hero .lead {{ color:var(--muted); margin-top:4px; }}
.hero .tally {{ font:11px/1.5 ui-monospace,"SF Mono",Consolas,monospace; color:var(--muted);
  margin-top:8px; }}

.empty {{ color:var(--muted); padding:28px 0; border-bottom:1px solid var(--rule); }}
.sr-only {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0);
  white-space:nowrap; }}

footer {{ margin-top:44px; padding-top:12px; border-top:1px solid var(--rule);
  font:11px/1.6 ui-monospace,"SF Mono",Consolas,monospace; color:var(--muted);
  display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; }}

@media (max-width:900px) {{
  .grid {{ grid-template-columns:1fr; }}
  .rail {{ position:static; display:flex; flex-wrap:wrap; gap:0; border-bottom:1px solid var(--rule); }}
  .rail .label, .rail .stat {{ display:none; }}
  .rail a {{ border-bottom:none; padding:8px 12px 8px 10px; }}
  .rail a + a {{ border-left:1px solid var(--rule); }}
}}
@media (max-width:620px) {{
  .cabinet {{ align-items:flex-start; flex-direction:column; gap:6px; }}
  .cabinet .cue {{ text-align:left; }}
  .rec {{ grid-template-columns:1fr; gap:3px; padding:12px 4px; }}
  .rec .tags {{ justify-content:flex-start; max-width:none; }}
}}
@media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>
</head>
<body>
<div class="shell">
{body}
  <footer><span>{footer}</span><span>{footer_right}</span></footer>
</div>
</body>
</html>
"""


def _tab_label(category: dict) -> str:
    return html.escape(category.get("name", category.get("slug", "")))


def _record_row(page: dict, accent: str, category_slug: str = "") -> str:
    """
    一条记录：日期 / 标题+摘要 / 标签，整行可点

    Args:
        page: 页面条目
        accent: 该分类的强调色
        category_slug: 非空时用于索引页的跨分类链接；分类页自身不需要分类段
    """
    slug = html.escape(page.get("slug", ""))
    href = f"./{html.escape(category_slug)}/{slug}/" if category_slug else f"./{slug}/"
    title = html.escape(page.get("title", ""))
    desc = html.escape(page.get("desc", ""))
    date = html.escape(page.get("date", ""))
    tags = "".join(
        f'<span class="tag">{html.escape(t)}</span>' for t in page.get("tags", [])
    )
    # 完整路径作为不可见的定位信息保留：发布验活依赖「标题与路径同时出现」，
    # 它也是这条记录在站点里的稳定地址，只是不必占据视觉空间。
    # 优先用事实源里的 path；缺失时按分类 + slug 拼出来
    full_path = page.get("path") or (
        f"{category_slug}/{page.get('slug', '')}/" if category_slug else f"{page.get('slug', '')}/"
    )
    path_marker = (
        f'<span class="sr-only">{html.escape(full_path)}</span>' if full_path else ""
    )

    return (
        f'      <a class="rec" href="{href}" title="{title}">\n'
        f'        <span class="date">{date}</span>\n'
        f'        <span class="title">{title}{path_marker}'
        + (f'<span class="gist">{desc}</span>' if desc else "")
        + "</span>\n"
        + (f'        <span class="tags">{tags}</span>\n' if tags else "")
        + "      </a>"
    )


def _cabinet(active: Optional[str] = None, right: str = "") -> str:
    cue = (
        f'<a href="./{html.escape(active)}/" style="color:var(--accent);text-decoration:none">'
        f"当前分类</a>"
        if active
        else ""
    )
    return (
        '  <header class="cabinet">\n'
        f'    <div class="name">{html.escape(SITE_TITLE)}'
        '<small>transit · hosted pages</small></div>\n'
        f'    <div class="cue">{cue}{right}</div>\n'
        "  </header>"
    )


def _sorted_pages(category: dict) -> list[dict]:
    return sorted(category.get("pages", []), key=lambda p: p.get("date", ""), reverse=True)


def render_index_page(registry: dict) -> str:
    """渲染索引页：左侧分类目录 + 右侧按分类分段的密集记录表"""
    categories = registry.get("categories", [])
    total_pages = sum(len(c.get("pages", [])) for c in categories)

    if not categories:
        body = (
            _cabinet()
            + '\n  <p class="empty">还没有发布任何页面。</p>'
        )
        return PAGE_TMPL.format(
            title=SITE_TITLE,
            description="按分类浏览已托管的页面",
            body=body,
            footer=f"{SITE_TITLE} · 由 transit 托管",
            footer_right=f"{total_pages} 个页面",
        )

    # 左侧目录
    rail_items = []
    for i, category in enumerate(categories):
        slug = category.get("slug", "")
        count = len(category.get("pages", []))
        rail_items.append(
            f'    <a href="#{html.escape(slug)}">'
            f'<span class="mark" style="width:9px;height:9px;border-radius:1px;'
            f'background:{CATEGORY_COLORS[i % len(CATEGORY_COLORS)]};display:inline-block"></span>'
            f"{_tab_label(category)}"
            f'<span class="count">{count}</span></a>'
        )
    rail = (
        '  <aside class="rail" aria-label="分类目录">\n'
        '    <div class="label">分类</div>\n'
        + "\n".join(rail_items)
        + f'\n    <div class="stat">{total_pages} 个页面 · {len(categories)} 个分类</div>\n'
        "  </aside>"
    )

    # 右侧分段
    sections = []
    for i, category in enumerate(categories):
        slug = category.get("slug", "")
        accent = CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
        pages = _sorted_pages(category)
        rows = "\n".join(_record_row(p, accent, slug) for p in pages)
        if not rows:
            rows = '      <p class="empty">该分类暂无页面。</p>'
        sections.append(
            f'    <section class="section" id="{html.escape(slug)}">\n'
            f'      <h2><span class="mark" style="background:{accent}"></span>{_tab_label(category)}'
            f'<span class="n">{len(pages):02d}</span></h2>\n'
            f"{rows}\n"
            "    </section>"
        )

    body = "\n".join(
        [
            _cabinet(),
            '  <div class="grid">',
            rail,
            '  <main class="records">',
            "\n".join(sections),
            "  </main>",
            "  </div>",
        ]
    )
    return PAGE_TMPL.format(
        title=SITE_TITLE,
        description="按分类浏览已托管的页面",
        body=body,
        footer=f"{SITE_TITLE} · 由 transit 托管",
        footer_right=f"{total_pages} 个页面 · {len(categories)} 个分类",
    )


def render_category_page(registry: dict, category_slug: str) -> Optional[str]:
    """渲染分类页：同款记录表，只保留该分类；分类不存在时返回 None"""
    categories = registry.get("categories", [])
    index = next((i for i, c in enumerate(categories) if c.get("slug") == category_slug), None)
    if index is None:
        return None

    category = categories[index]
    accent = CATEGORY_COLORS[index % len(CATEGORY_COLORS)]
    name = category.get("name", category_slug)
    pages = _sorted_pages(category)

    rows = "\n".join(_record_row(p, accent) for p in pages)
    if not rows:
        rows = '      <p class="empty">该分类暂无页面。</p>'

    hero = (
        '  <header class="hero">\n'
        f'    <div class="crumb"><a href="../../pages/">{html.escape(SITE_TITLE)}</a> / '
        f"{_tab_label(category)}</div>\n"
        f"    <h1>{html.escape(name)}</h1>\n"
        + (f'    <p class="lead">{html.escape(category["description"])}</p>\n' if category.get("description") else "")
        + f'    <div class="tally">{len(pages)} 个页面</div>\n'
        "  </header>"
    )

    # 页眉已经写明分类，不再重复一个同名分组标题
    body = "\n".join(
        [
            hero,
            '  <section class="section">',
            rows,
            "  </section>",
        ]
    )
    return PAGE_TMPL.format(
        title=f"{name} · {SITE_TITLE}",
        description=category.get("description") or f"{name} 分类下的页面",
        body=body,
        footer=f"{SITE_TITLE} · 由 transit 托管",
        footer_right=f"{len(pages)} 个页面",
    )
