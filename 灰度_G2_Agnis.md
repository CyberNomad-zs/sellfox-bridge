# Agnis 单店灰度 G2 · 操作说明

> 更新：2026-07-21  
> 状态：**材料已就绪，默认未启动 G2**（当前请继续 G1 或 dry-run）

---

## 1. G1 → G2 差异

| 项 | G1 | G2 |
|---|---|---|
| 店铺 | 仅 Agnis `396706` | 同左 |
| dry-run | 关 | 关 |
| 有渠道 | 本地 `CHANNEL_ASSIGNED`，不调赛狐写 | 同左 |
| **物流下单** | **关** | **开** `applyTrackNo` **真推仓** |
| 称重回传 step4 | 基本无 ORDERED | 下单成功后可能进入 ORDERED，WMS 出库后会尝试回传 |
| 无渠道 | 人工指派 | 同左 |

**G2 会真实调用赛狐「物流下单」API，单会进 WMS，不是演练。**

---

## 2. 文件

| 文件 | 用途 |
|---|---|
| `config/config.g2-agnis.yaml` | G2 专用（`auto_apply_track_no: true`） |
| `run_g2_agnis.bat` | 启动 G2（需输入 `YES`） |
| `config/config.g1-agnis.yaml` | G1（不下单）— 回退用 |
| `run_g1_agnis.bat` | 回退到 G1 |

代码增强（为 G2）：

- `step3` 打印真写下单列表与 API 返回  
- 返回无明细时**不再盲目**全部标 `ORDERED`  
- 可选 `run.order_channel_names`：只对列出的渠道名自动下单  

---

## 3. 启动前：本地会立刻被下单的单

G2 第一轮会对 **Agnis + state=CHANNEL_ASSIGNED** 调 `applyTrackNo`。

启动前请查库 / 已知：

| 包裹 | 渠道 | 启动 G2 后 |
|---|---|---|
| **P2AS6TCD63996** | BLACKCAT-RM | **首轮就会物流下单** |

若暂不想下这一单：

1. 先在 G1 停掉后把该单状态改掉，或  
2. 在 `config.g2-agnis.yaml` 设  
   `order_channel_names: ["昇新海外仓-RM", "昇新海外仓-DPD"]`  
   （则 BLACKCAT-RM 的 63996 不会被 step3 选中）

---

## 4. 启动前检查清单

- [ ] G1 已有多笔 `CHANNEL_ASSIGNED` 成功样例  
- [ ] 关掉 G1 / dry-run（勿双开）  
- [ ] **Agnis 不要**同时 automation 全流程真跑  
- [ ] 知悉 **63996 会被下单**（或已用 order_channel_names 排除）  
- [ ] 赛狐 IP 白名单有效  
- [ ] 已读「回退」：已下单无法靠停进程撤销  

---

## 5. 如何启动 G2

1. 停 G1：结束 `g1-agnis` 的 python  
2. 双击 `run_g2_agnis.bat` → 输入 **`YES`**  
3. 日志期望：

```text
customer=金猫商贸-G2-Agnis dry_run=False
step3 物流下单(真写) 共 N 单: ['P2AS6TCD63996', ...]
step3 applyTrackNo 返回: {...}
P2AS6TCD63996 物流下单成功 → ORDERED
```

命令行：

```text
python main.py --config config/config.g2-agnis.yaml
```

（不要加 `--dry-run`，否则又不会真下单。）

---

## 6. 成功 / 失败怎么看

| 日志 | 含义 |
|---|---|
| `物流下单成功 → ORDERED` | 赛狐已接单推仓 |
| `物流下单失败` + FAILED | 看 msg（库存/渠道/重复下单等） |
| `无 successData/failData` | 需人工打开赛狐核对该包裹是否已下单 |
| 之后 step4 dry 类 / 真回传 | WMS 出库+运单后可能称重发货（注意重量为空时可能失败） |

赛狐网页：该单应从「待处理」进入后续状态（物流下单/三方仓等）。  
WMS：昇新渠道查金猫 key；BLACKCAT 查黑猫 key。

---

## 7. 回退

| 场景 | 做法 |
|---|---|
| 立刻停新下单 | 结束 G2 进程 → 开回 `run_g1_agnis.bat` 或 dry-run |
| 已经 applyTrackNo 成功 | **不能**靠回退撤销；在赛狐/WMS 按业务继续或拦截 |
| 误开想只读 | `run_dryrun.bat` |

---

## 8. 与 automation

G2 期间 Agnis：

- **不要**再跑 automation 物流下单/全流程真跑  
- 仓内拣货打单仍可在 WMS 网页操作  

---

## 9. Phase A 已落地（状态机/回传兜底）

| 项 | 行为 |
|---|---|
| FAILED 复活 | to_process 再次出现且赛狐**已有可用渠道** → NEW，本轮可认渠道 |
| 陈旧 NEW | `stale_new_days`（默认 3）不在 to_process → `STALE`，不再每轮刷日志 |
| step4 重量 | `ship_confirm_mode: auto`：有 weight/sku 估重 → weighing，否则 **quick_outbound** |
| track_no | 出库有运单时写入本地 `track_no` |
| step1b 幂等 | 拉赛狐 `apply_track_no`，本地 NEW/CHANNEL_ASSIGNED/FAILED/STALE → `ORDERED`，避免重复下单 |
| 下单失败文案 | 含「已下单/重复」等 → 同步 ORDERED 而非 FAILED |
| step4 连续失败 | `step4_fail_alert_after`（默认 5）次升级告警 |

## 10. G2 之后（未授权勿做）

| 阶段 | 内容 |
|---|---|
| G2 稳 | 多单下单成功、WMS 有单 |
| G3 | 跟完 step4 闭环（63996 等仓发货） |
| G4 | 扩 HomeCove / Twilight |

---

## 10. 当前默认建议

**先不要启动 G2。**  
确认 63996 可以真下单、且 Agnis 无 automation 冲突后，再双击 `run_g2_agnis.bat`。

若要启动，明确说：**「启动 G2」**。
