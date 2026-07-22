# 建议优先补克重的 SKU 清单

> 生成：2026-07-21 14:32  
> 来源：`bridge.log`「无预估重量档案」统计 + 今日业务语义对齐时的 to_process 快照  
> 注：二次实时拉单时赛狐 API 曾超时，在途包裹数以今日已成功拉单结果为准  
> 缺克重 **14** 个（合并同 SKU 展示）；`sku_weights` 已配置 **0** 个

## 优先级

| 级 | 含义 | 是否必须马上补 |
|---|---|---|
| **P0** | 出现在无渠道包裹 | 若要自动选渠道则必须；人工指派可暂不补 |
| **P1** | 当前/今日待处理在途、日志高频 | 灰度称重发货前建议补（重量兜底） |
| **P2** | 仅历史日志 | 可后补 |

单位：**克 (g)**，填入 `config/config.yaml` → `sku_weights`。

| 优先级 | SKU | 日志警告次数 | 在途包裹(估) | 无渠道 | 说明 | 建议克重(g) |
|---|---|---:|---:|---:|---|---|
| P0 | `JMCATZSNG` | 1 | 1 | 1 | 无渠道单 P2AS6TCD63872 |  |
| P1 | `JMCAT4DKQ` | 126 | 3 | 0 | 待处理多次，日志最高频 |  |
| P1 | `JMCATJTXL` | 126 | 3 | 0 | 待处理多次，日志最高频 |  |
| P1 | `JMCATSWJJ` | 84 | 2 | 0 | 日志高频 |  |
| P1 | `JMCATTZCS` | 48 | 1 | 0 | 日志高频 |  |
| P1 | `UK-NL-GA-ZT` | 48 | 1 | 0 | 昇新-RM |  |
| P1 | `VIPTZ10` | 48 | 1 | 0 | 昇新-RM |  |
| P1 | `JMCATSLXD` | 42 | 1 | 0 | 日志高频 |  |
| P1 | `JMCATXJZD` | 42 | 1 | 0 | 日志高频 |  |
| P1 | `VIPPBNL` | 37 | 1 | 0 | 昇新-DPD（白板类） |  |
| P1 | `UK-LDV-TS-W` | 10 | 1 | 0 | 在途 |  |
| P1 | `UK-NVL-WB` | 21 | 1 | 0 | 日志偶发带尺寸后缀 `90x60CM`，请确认正式编码 |  |
| P2 | `JMCATLCTB` | 1 | 0 | 0 | 仅 7/16 历史 |  |
| P2 | `UK-CS-TL-50PCS` | 1 | 0 | 0 | 仅 7/16 历史 |  |

## 建议先填（P0 + P1）粘贴模板

```yaml
sku_weights:
  JMCATZSNG: 0      # TODO 填克重(g)  P0 无渠道
  JMCAT4DKQ: 0      # TODO
  JMCATJTXL: 0      # TODO
  JMCATSWJJ: 0      # TODO
  JMCATTZCS: 0      # TODO
  UK-NL-GA-ZT: 0    # TODO
  VIPTZ10: 0        # TODO
  JMCATSLXD: 0      # TODO
  JMCATXJZD: 0      # TODO
  VIPPBNL: 0        # TODO
  UK-LDV-TS-W: 0    # TODO
  UK-NVL-WB: 0      # TODO 确认是否即 90x60CM 规格
```

## 说明

- **业务已定（2026-07-21）：无渠道单 = 人工在赛狐指派渠道**，不靠程序自动选。  
  → 本清单对主路径 **非阻塞**；P0 也改为「人工指派即可」，不必为选渠道而先填克重。
- 当前 `keep_existing_channel: true`：**有渠道单不依赖克重**也能 dry-run 保留渠道。
- 克重用途收缩为：以后称重发货 `weighingShipment` 重量兜底（灰度回传前再补即可）。
- 请业务按仓库计费重/称重习惯填**整数克**；订单数量由 `qty` 相乘，这里填单件重。
- 日志次数高 ≠ 缺货严重，多半是 dry-run 每 5 分钟扫一遍重复刷警告。
