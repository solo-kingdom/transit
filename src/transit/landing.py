"""
根路径产品说明页渲染

根路径是服务的对外门面：访问者第一眼应看懂这是个什么服务、怎么用，
以及能去哪里。页面用服务端渲染（同一个进程，不必再拉前端构建），
中英文两版共用一套样式，靠查询参数切换。

机器可读的服务信息仍在 /health；本页只在页脚展示 service / version。
"""

import html

# 服务名与版本由调用方注入（来自 settings），避免此处再读一遍配置
DEFAULT_TITLE = "Transit · 文件中转与页面托管"

# 页面底部展示的外链，中英文共用
LINKS = [
    (
        "https://exploring.fun",
        "exploring.fun",
        "探索与实验的角落，随手记下做过的尝试。",
        "A corner for experiments and explorations.",
    ),
    (
        "https://wii.pub",
        "wii.pub",
        "个人主页，聚合各处产出与近况。",
        "Personal homepage aggregating works and updates.",
    ),
    (
        "https://solo.wii.pub",
        "solo.wii.pub",
        "个人作品集，展示做过的项目与作品。",
        "Portfolio showcasing projects and works.",
    ),
    (
        "https://dove.wii.pub",
        "dove.wii.pub",
        "羽知，个人知识库，沉淀主题、标签与订阅。",
        "Dove, a personal knowledge base of topics and tags.",
    ),
]

# 中英文两套文案。键一一对应，渲染时只按 lang 取值。
COPY = {
    "zh": {
        "lang": "zh-CN",
        "toggle": "English",
        "toggle_href": "/?lang=en",
        "tagline": "一个自足链接驱动的文件中转与页面托管服务。",
        "intro": (
            "Transit 把文件上传变成一条可直接分享的链接：上传后返回的地址自带访问凭据，"
            "发给任何人都能打开，无需再配认证。它同时能托管 HTML 页面，"
            "把一次性的说明、报告或专题发布成一个公开可访问的网址。"
        ),
        "features_title": "能做什么",
        "features": [
            ("自足链接", "上传即得带凭据的完整链接，拿到链接就能取件，不用再带认证头。"),
            ("按类型展示", "文本、图片、音视频与 PDF 直接在浏览器打开或播放，音视频支持拖动进度。"),
            ("页面托管", "发布单文件 HTML 或整包页面目录，按分类组织，发布后公开可浏览。"),
            ("安全隔离", "上传文件自动去掉执行权限，元信息文件不可被直接取走，读写凭据分离。"),
        ],
        "usage_title": "怎么用",
        "usage": [
            ("上传文件", "curl --upload-file ./report.pdf https://transit.wii.pub/"),
            ("发布页面", "curl -X POST https://transit.wii.pub/pages/publish -H \"Authorization: Bearer <write-token>\" -F category=note -F slug=hello -F title=你好 -F desc=摘要 --form-string html='<h1>正文</h1>'"),
            ("浏览页面", "https://transit.wii.pub/pages/"),
        ],
        "links_title": "看看别处",
        "footer_note": "由 transit 托管",
    },
    "en": {
        "lang": "en",
        "toggle": "中文",
        "toggle_href": "/",
        "tagline": "A file transit and page hosting service built around self-sufficient links.",
        "intro": (
            "Transit turns an upload into a link you can hand to anyone: the returned address "
            "carries its own access credential, so it just works without extra auth headers. "
            "It also hosts HTML pages, so a one-off note, report or write-up can go live at a "
            "public URL in one request."
        ),
        "features_title": "What it does",
        "features": [
            ("Self-sufficient links", "An upload returns a full URL with its own credential — whoever has the link can fetch the file, no auth header needed."),
            ("Type-aware display", "Text, images, audio, video and PDF render or play in the browser; media supports range requests for seeking."),
            ("Page hosting", "Publish a single-file HTML page or a full bundle, organised by category, public once released."),
            ("Safety first", "Uploaded files lose their execute bit, metadata files cannot be fetched, and read/write credentials stay separate."),
        ],
        "usage_title": "How to use",
        "usage": [
            ("Upload a file", "curl --upload-file ./report.pdf https://transit.wii.pub/"),
            ("Publish a page", "curl -X POST https://transit.wii.pub/pages/publish -H \"Authorization: Bearer <write-token>\" -F category=note -F slug=hello -F title=Hello -F desc=Summary --form-string html='<h1>Body</h1>'"),
            ("Browse pages", "https://transit.wii.pub/pages/"),
        ],
        "links_title": "Elsewhere",
        "footer_note": "hosted by transit",
    },
}

LANDING_TMPL = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%2316324A'/%3E%3Ccircle cx='8' cy='8' r='3.5' fill='%23F4F5F2'/%3E%3C/svg%3E">
<style>
:root {{ --paper:#F4F5F2; --card:#FFFFFF; --ink:#16324A; --body:#33383E;
  --line:#D8DCD6; --accent:#35618F; }}
* {{ box-sizing:border-box; margin:0; }}
body {{ background:var(--paper); color:var(--body);
  font:16px/1.75 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }}
.wrap {{ max-width:760px; margin:0 auto; padding:56px 24px 64px; }}
a {{ color:var(--accent); }}
.top {{ display:flex; align-items:baseline; justify-content:space-between; gap:16px; }}
.brand {{ font:13px/1 ui-monospace,"SF Mono",Consolas,monospace; color:#8A9198;
  letter-spacing:.04em; text-transform:uppercase; }}
.lang {{ font:13px/1 ui-monospace,"SF Mono",Consolas,monospace; }}
h1 {{ font-family:"Noto Serif SC","Songti SC",SimSun,serif; font-weight:600;
  font-size:36px; line-height:1.25; color:var(--ink); margin:22px 0 12px; }}
.tagline {{ font-size:19px; color:var(--ink); margin-bottom:20px; }}
.intro {{ color:#4B5259; max-width:66ch; }}
h2 {{ font-family:"Noto Serif SC","Songti SC",SimSun,serif; font-weight:600;
  font-size:20px; color:var(--ink); margin:44px 0 14px; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-top:3px solid var(--accent);
  padding:16px 18px; }}
.card h3 {{ font-family:"Noto Serif SC","Songti SC",SimSun,serif; font-weight:600;
  font-size:17px; color:var(--ink); margin-bottom:6px; }}
.card p {{ font-size:14px; line-height:1.65; color:#6A7178; }}
.snippet {{ background:var(--card); border:1px solid var(--line); padding:14px 16px;
  margin-bottom:10px; }}
.snippet .label {{ font-size:13px; color:#8A9198; margin-bottom:8px; }}
.snippet code {{ display:block; font:13px/1.7 ui-monospace,"SF Mono",Consolas,monospace;
  color:var(--ink); white-space:pre-wrap; word-break:break-all; }}
.links {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
.link {{ display:block; background:var(--card); border:1px solid var(--line); border-left:3px solid var(--accent);
  padding:14px 18px; text-decoration:none; }}
.link .host {{ font:13px/1.4 ui-monospace,"SF Mono",Consolas,monospace; color:var(--accent); }}
.link .note {{ font-size:13.5px; line-height:1.6; color:#6A7178; margin-top:4px; }}
footer {{ margin-top:48px; padding-top:16px; border-top:1px solid var(--line);
  font:12px/1.7 ui-monospace,"SF Mono",Consolas,monospace; color:#8A9198; }}
@media (max-width:620px) {{
  h1 {{ font-size:29px; }}
  .grid, .links {{ grid-template-columns:1fr; }}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <span class="brand">transit</span>
    <a class="lang" href="{toggle_href}">{toggle}</a>
  </div>
  <h1>{heading}</h1>
  <p class="tagline">{tagline}</p>
  <p class="intro">{intro}</p>
{features}
{usage}
{links}
  <footer>{footer}</footer>
</div>
</body>
</html>
"""


def _feature_cards(copy: dict) -> str:
    """渲染「能做什么」的四张卡片"""
    cards = "\n".join(
        f'    <div class="card"><h3>{html.escape(t)}</h3><p>{html.escape(d)}</p></div>'
        for t, d in copy["features"]
    )
    return (
        f'  <h2>{html.escape(copy["features_title"])}</h2>\n'
        f'  <div class="grid">\n{cards}\n  </div>'
    )


def _usage_blocks(copy: dict) -> str:
    """渲染「怎么用」的命令片段"""
    blocks = "\n".join(
        f'    <div class="snippet"><div class="label">{html.escape(label)}</div>'
        f"<code>{html.escape(cmd)}</code></div>"
        for label, cmd in copy["usage"]
    )
    return f'  <h2>{html.escape(copy["usage_title"])}</h2>\n{blocks}'


def _link_cards(lang: str, copy: dict) -> str:
    """渲染外链卡片，按语言选取说明文案"""
    cards = "\n".join(
        f'    <a class="link" href="{url}"><span class="host">{html.escape(host)}</span>'
        f'<p class="note">{html.escape(note_zh if lang == "zh" else note_en)}</p></a>'
        for url, host, note_zh, note_en in LINKS
    )
    return f'  <h2>{html.escape(copy["links_title"])}</h2>\n  <div class="links">\n{cards}\n  </div>'


def render_landing_page(lang: str = "zh", service: str = "", version: str = "") -> str:
    """
    渲染根路径产品说明页

    Args:
        lang: 语言，只认 "zh" 与 "en"，其余回落到中文
        service: 服务名，用于页脚
        version: 版本号，用于页脚

    Returns:
        完整的 HTML 文档
    """
    if lang not in COPY:
        lang = "zh"
    copy = COPY[lang]

    identity = f"{service} v{version}".strip() if service else "transit"
    footer = f"{html.escape(identity)} · {html.escape(copy['footer_note'])}"

    return LANDING_TMPL.format(
        lang=copy["lang"],
        title=DEFAULT_TITLE if lang == "zh" else "Transit · File transit & page hosting",
        description=html.escape(copy["tagline"]),
        toggle_href=copy["toggle_href"],
        toggle=html.escape(copy["toggle"]),
        heading="Transit",
        tagline=html.escape(copy["tagline"]),
        intro=html.escape(copy["intro"]),
        features=_feature_cards(copy),
        usage=_usage_blocks(copy),
        links=_link_cards(lang, copy),
        footer=footer,
    )
