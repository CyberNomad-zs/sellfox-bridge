# 赛狐开放 API 参考

> 本文件由项目文档整理导出，供外部对接或归档使用。  
> 来源：`README.md`、`项目说明.md`、实际联调记录。  
> 导出时间：2026-07-21

---

## 1. 接入信息

| 项 | 值 |
|---|---|
| 接入域名 | `https://openapi.sellfox.com` |
| 官方文档 | `https://sellfoxapi.apifox.cn` |
| 文档访问密码 | `VZKGdd0Q` |
| 协议方法 | 全部接口均为 **POST** |
| 数据格式 | JSON，业务参数放在 body；鉴权参数放在 query |
| 网络限制 | 有 **IP 白名单**，不在白名单内会返回 `40005` |

---

## 2. 认证与签名

### 2.1 获取 access_token

- 接口：`GET /api/oauth/v2/token.json`
- 有效期：**24 小时**
- 需要缓存，失效后重新获取
- 项目中的 token 缓存逻辑见 `bridge/clients/sellfox.py`

### 2.2 业务接口签名规则

签名算法：**HMAC-SHA256**

签名字符串（参数名按字典序排序后拼接）：

```text
access_token=...&client_id=...&method=post&nonce=...&timestamp=...&url=...
```

- `timestamp` 使用**毫秒**时间戳
- `url` 为接口路径（如 `/api/packageShip/v1/getPackagePage.json`）
- **请求 body 不参与签名**
- 使用 `client_secret` 作为 HMAC 密钥

### 2.3 IP 白名单

- 错误码 `40005` 表示当前出口 IP 不在白名单
- 当前调试出口 IP：`49.77.234.254` / `222.94.107.67`（南京电信家宽，动态可变）
- 正式部署建议放在固定 IP 服务器（如 WMS 服务器 `193.112.93.60`）并加入白名单

---

## 3. 项目已接入接口清单

| 业务用途 | 接口路径 | 项目介入阶段 |
|---|---|---|
| 拉取包裹列表 | `/api/packageShip/v1/getPackagePage.json` | step1_discover |
| 查询物流渠道 | `/api/packageShip/queryShipChannel.json` | step2_assign |
| 指派仓库/渠道 | `/api/packageShip/updatePackageDetail.json` | step2_assign |
| 物流下单 | `/api/packageShip/applyTrackNo.json` | step3_order |
| 称重发货 | `/api/packageShip/weighingShipment.json` | step4_close |
| 快速出库（备用） | `/api/packageShip/quickOutbound.json` | 备用 |
| 仓库列表 | `/api/warehouseManage/warehouseList.json` | 配置校验 |

### 3.1 关键参数说明

- `packageStatus=to_process`：拉取"待处理"包裹
- `logisticsType=1`：查询三方仓物流渠道
- 赛狐包裹号字段：`packageSn`，与 WMS 的 `platformOrderNo` 一一对应

---

## 4. 赛狐包裹生命周期

```text
to_audit(待审核) → to_process(待处理) → apply_track_no(物流下单) → to_print(待打单) → has_shipped(已发货)
```

本程序当前主要介入 `to_process` 之后阶段：

- `to_process`：选渠道 / 指派仓库
- `apply_track_no`：触发物流下单
- `has_shipped` 之后：由 WMS 出库状态触发称重发货回传

---

## 5. 本地状态机

程序在本地 SQLite（`bridge.db`）维护如下状态：

```text
NEW → CHANNEL_ASSIGNED → ORDERED → WMS_SHIPPED → CLOSED
```

任一环节失败会进入 `FAILED`，进入重试队列或触发告警。

---

## 6. 错误码速查

| 错误码 | 含义 | 常见原因 / 处理 |
|---|---|---|
| `40005` | IP 不在白名单 | 出口 IP 变动或走了代理；确认客户端 `trust_env=False` 强制直连 |

---

## 7. 项目实现位置

- 客户端封装：`bridge/clients/sellfox.py`
- 业务流水线：`bridge/pipeline.py`
- 渠道决策：`bridge/selector.py`
- 本地状态存储：`bridge/store.py`
- 配置入口：`config/config.yaml`

---

## 8. 已知限制与注意事项

1. **地址编辑无 API**：赛狐没有地址编辑接口，地址修剪只能做"检测 + 告警转人工"。
2. **待审核/拆包未接入**：`auditPackage.json`、`splitPackage.json` 在当前版本未实现。
3. **称重发货需要重量**：WMS 不返回实际称重重量，当前用 SKU 预估重量兜底，或改用 `quickOutbound`（不需要重量）。
