---
name: transit
description: >
  操作 Transit（文件中转与页面托管）：上传/取件、发布公开或受保护页面（含 zip 多文件）、
  在多实例间路由与登记实例。用户点名 transit、transit.wii.pub、transit.lan、上传取件、
  发布页面，或要为 Agent 选用某个 Transit 实例时使用。可从任意运行中的实例拉取本文件：
  GET {base}/skill.md。
---

# transit — 文件中转与页面托管

> 本文件是唯一事实源：运行中的服务根路径会**嵌入**它，并提供 `GET /skill.md` 原文。
> 改 skill 只需改仓库里这一份，不必同步落地页文案。

## 何时用

- 上传文件、取回链接、发布 HTML / zip 页面
- 在多个 Transit 部署之间选型（公网 / 内网 / 自建）
- 给实例补注释、使用场景，或登记新实例

## 多实例台账（事实源）

个人部署清单维护在 **agent-data**（不进本开源仓，避免把私有 URL/节点写死进镜像）：

```text
{agent-data}/profile/services/transit/instances.md
```

用 `agent-data` skill 的 `locate.sh` 定位仓库根。没有 agent-data 时，用环境变量
`TRANSIT_INSTANCES_PATH` 指向同结构的本地文件；仍没有则只按用户点名的 base URL 操作，
并提示补登记。

条目模板见同目录 [`instances.example.md`](instances.example.md)。每条至少含：

| 字段 | 含义 |
| --- | --- |
| `id` | 稳定短名（如 `tchk`、`lnv`） |
| `base_url` | 对外根 URL（无尾斜杠），如 `https://transit.wii.pub` |
| `visibility` | `public` / `lan` / `private` |
| `use_when` | 使用场景（何时该选它） |
| `notes` | 自由注释 |
| `senv_group` | 写/读 token 所在 senv 组（可选；明文永不写入台账） |
| `write_token_key` / `read_token_key` | senv 键名（可选） |
| `status` | `active` / `planned` / `retired` |

## 实例路由（动手前必做）

按顺序收敛到**唯一** `base_url`，再调 API：

1. **用户点名**实例 id、域名或 URL → 用该条。
2. **场景命中** `use_when`（如「公网分享」→ public、「仅内网」→ lan）且只命中一条 → 用该条。
3. **当前机器可及性**：仅内网可达 lan、公网任务优先 public——仍只剩一条才自动选。
4. **否则停下来问用户**：列出候选 `id` / `base_url` / `use_when`，请用户指定；不要猜。

路由结果在本轮对话内复用；换任务或用户改口再重新判定。

## 写凭据

- 开了 `AUTH_ENABLED` 时，上传与 `/pages/publish` 需要写 token。
- 从 senv 取：`senv env get -g <senv_group> <write_token_key>`（键名以实例台账为准）。
- **禁止**把 token 写进 skill、台账、commit 或聊天落盘；命令行临时注入即可。
- 传法（命中第一个非空）：`Authorization: Bearer` → `X-Auth-Token` → 表单 `token` → query `token`。

## API 速查（`{base}` = 实例 base_url）

### 健康

```bash
curl -fsS "{base}/health"
# → {"status":"healthy"}
```

### 上传文件（默认受保护）

```bash
# 默认 → /protect/{token}/{filename}
curl -fsS -H "Authorization: Bearer $WRITE_TOKEN" \
  -F file=@./report.pdf "{base}/"

# 公开文件
curl -fsS -H "Authorization: Bearer $WRITE_TOKEN" \
  -F file=@./report.pdf -F path=/public "{base}/"

# 可选：expires_in 秒；过期后 410，磁盘不自动删
curl -fsS -H "Authorization: Bearer $WRITE_TOKEN" \
  -F file=@./report.pdf -F expires_in=3600 "{base}/"
```

`path` 与 `protected` 皆可选：都空则文件默认 `/protect`；只填一边则推算另一边；都填须一致，否则 400。

### 取件

- 受保护：`GET {base}/protect/{token}/{filename}`（旧别名 `/f/...`）
- 公开：`GET {base}/public/{encoded}/{filename}`
- 链接自足，**不要**再带全局读 token；公网若返回 http 链接，curl 加 `-L` 跟随 https。

### 发布页面（多文件用 zip）

```bash
# 公开页（默认 /pages）
curl -fsS -H "Authorization: Bearer $WRITE_TOKEN" \
  -F category=guide -F slug=hello -F title=标题 -F desc=摘要 \
  -F category_name=指南 --form-string html='<h1>正文</h1>' \
  "{base}/pages/publish"

# HTML + 静态资源：打 zip（根目录须有 index.html），一次上传
cd site && zip -r ../site.zip . && cd ..
curl -fsS -H "Authorization: Bearer $WRITE_TOKEN" \
  -F category=guide -F slug=site -F title=站点 -F desc=摘要 \
  -F category_name=指南 -F protected=true -F bundle=@site.zip \
  "{base}/pages/publish"
# → url: {base}/protect/{token}/guide/site/
```

页面侧：`path`/`protected` 都空默认 `/pages`（公开）。受保护页不进公开索引，也不能从 `/pages/{cat}/{slug}/` 绕过。

### Agent 拉取本 skill

```bash
curl -fsS "{base}/skill.md" -o transit-SKILL.md
```

## 登记 / 更新实例

1. 打开 `{agent-data}/profile/services/transit/instances.md`（或 `TRANSIT_INSTANCES_PATH`）。
2. 按 `instances.example.md` 追加或改字段；`status=planned` 未上线的不要自动路由选中。
3. 凭据只写 senv 组名与键名，不写值。
4. 改完可用「列实例」向用户确认一张表：`id | base_url | use_when | status`。

## 门禁

- 对实例的**写操作**（上传、发布、删数据）需用户意图覆盖该实例；「继续」不自动换实例。
- 部署 / 改 compose / 推镜像走 `series-deploy` + 对应 `deploy/<node>/transit/`，本 skill 不替代发版。
- 只读探活（`/health`、公开 `/pages/`）可直接做。

## 完成标准

- 已选定并复述 `id` + `base_url`（或已向用户确认）。
- 写操作使用该实例的写 token，且未把密钥写入文件。
- 上传/发布响应里的 URL 与预期命名空间一致（`/protect` / `/public` / `/pages`）。
- 若改了实例台账，已保存且能列出最新条目。
