# 单店灰度 G1 · 操作说明

> 更新：2026-07-21  
> **当前运行：Agnis G1**（`config.g1-agnis.yaml` / `run_g1_agnis.bat`）  
> HomeCove G1 配置仍保留，可随时切回。

---

## 1. G1 是什么 / 不是什么

| 项 | G1 |
|---|---|
| 店铺 | **当前 Agnis** `396706`（备选 HomeCove `398202`） |
| dry-run | **关闭**（会推进本地状态） |
| 自动物流下单 | **关闭** `auto_apply_track_no: false` |
| 有渠道单 | 本地 `NEW → CHANNEL_ASSIGNED`，**不调**赛狐写接口 |
| 无渠道单 | 告警，**人工在赛狐指派**（已定策略） |
| 称重回传 step4 | 本地无 ORDERED 单时基本不跑；且本阶段不主动下单 |
| Agnis / Twilight | **不处理**（白名单 + step 过滤） |

**G1 不是全自动发货。** 推仓仍靠网页/automation；bridge 只在 HomeCove 上练「发现 → 本地认渠道」。

---

## 2. 文件

| 文件 | 用途 |
|---|---|
| `config/config.yaml` | 三店 **dry-run 观察**（默认） |
| `config/config.g1-agnis.yaml` | **当前 G1**（仅 Agnis） |
| `config/config.g1-homecove.yaml` | 备选 G1（仅 HomeCove） |
| `run_dryrun.bat` | 日常只读 |
| `run_g1_agnis.bat` | 启动 Agnis G1（需输入 `YES`） |
| `run_g1_homecove.bat` | 启动 HomeCove G1 |
| `bridge.db` | 共用本地库；step2/3/4 按白名单过滤店铺 |

代码增强：`pipeline._rows_for_step` 按 `shop_whitelist` 过滤，避免库里其它店历史单被误推进。

---

## 3. 启动前检查清单

- [ ] dry-run 已观察 ≥1～2 天，渠道/双 WMS 正常  
- [ ] 关掉正在跑的 `run_dryrun.bat`（同一机器勿双开抢库）  
- [ ] **HomeCove 不要**同时跑 automation 全流程真跑（可对其它店）  
- [ ] 赛狐 IP 白名单有效（无 40005）  
- [ ] 已读本节「回退」  

---

## 4. 如何启动 G1

1. 停 dry-run：窗口 `Ctrl+C`  
2. 双击 `run_g1_homecove.bat`  
3. 提示时输入大写 **`YES`**  
4. 日志应类似：

```text
customer=金猫商贸-G1-HomeCove
WMS profile=jinmao ...
WMS profile=blackcat ...
----- 第 1 轮开始 -----
step1: 赛狐待处理 N 条 ...   # 仅 HomeCove
Pxxxx 保留已有渠道 xxx → CHANNEL_ASSIGNED (未调写接口)
```

**没有** `[dry-run]` 前缀；**不应**出现 `物流下单` / `weighingShipment`。

命令行等价：

```text
python main.py --config config/config.g1-homecove.yaml
```

（不要加 `--dry-run`，否则又变只读。）

---

## 5. 观察什么（G1 成功标准）

| 看 | 期望 |
|---|---|
| 拉单店铺 | 仅 HomeCove |
| 有渠道 | 本地变为 `CHANNEL_ASSIGNED`，赛狐渠道不变 |
| 无渠道 | FAILED/告警，赛狐人工补渠道后下轮可保留 |
| 其它店 | 日志可有「白名单过滤跳过」；不写其它店 |
| 写接口 | 无 applyTrackNo / 称重发货（有渠道路径） |

抽查：赛狐网页 HomeCove 待处理渠道 vs 日志一致。

---

## 6. 回退（立刻）

1. G1 窗口 `Ctrl+C`  
2. 双击 `run_dryrun.bat`（三店只读）  
3. 需要时用 automation / 网页处理 HomeCove  
4. 不必删 `bridge.db`（状态可留；dry-run 不写外向接口）

若误开 `auto_apply_track_no`：先停进程，把 G1 config 改回 `false`，再评估是否有单已推仓。

---

## 7. G1 之后（未授权勿做）

| 阶段 | 动作 |
|---|---|
| G1 稳 1～2 天 | 保持 |
| G2 | 仍 HomeCove，`auto_apply_track_no: true`（先昇新渠道更稳） |
| G3 | step4 称重回传（需克重或 quick 模式） |
| G4 | 扩 Agnis / Twilight |

---

## 8. 与 automation 分工（G1）

| 系统 | HomeCove | 其它店 |
|---|---|---|
| bridge G1 | 本地认渠道 | 不碰 |
| automation | **建议暂停真跑** 或只人工 | 可照旧 |
| 网页 | 无渠道指派、物流下单 | 照旧 |

---

## 9. 当前默认建议

**先不要启动 G1。**  
继续 `run_dryrun.bat` 观察；准备好后再双击 `run_g1_homecove.bat` 并输入 YES。
