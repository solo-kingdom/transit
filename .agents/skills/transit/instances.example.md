# Transit 实例台账（示例）

> 复制到 agent-data：`profile/services/transit/instances.md`（或设 `TRANSIT_INSTANCES_PATH`）。
> 勿把真实 token 写入本文件。

## 实例

### tchk

- **id**: `tchk`
- **base_url**: `https://transit.wii.pub`
- **visibility**: `public`
- **status**: `active`
- **use_when**: 公网分享文件或页面；需要外网可打开的链接
- **notes**: 腾讯云 HK；数据在 tchk 宿主 bind mount；与内网实例数据不通
- **senv_group**: `svc-transit`
- **write_token_key**: `TRANSIT_WRITE_TOKEN`
- **read_token_key**: `TRANSIT_READ_TOKEN`
- **deploy**: `deploy/tchk/transit/`（agent-data）

### lnv

- **id**: `lnv`
- **base_url**: `http://transit.lan`
- **visibility**: `lan`
- **status**: `planned`
- **use_when**: 仅内网上传/取件，不经公网
- **notes**: 与 tchk 数据独立；DOWNLOAD_HOST 无 scheme 时需 http 通道
- **senv_group**: `svc-transit`
- **write_token_key**: `TRANSIT_WRITE_TOKEN`
- **read_token_key**: `TRANSIT_READ_TOKEN`
- **deploy**: `deploy/lnv/transit/`（agent-data）
