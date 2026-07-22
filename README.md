# sellfox-bridge 赛狐 ↔ WMS 发货桥接程序

用赛狐开放 API + 双 WMS API 打通金猫商贸三店（Agnis / HomeCove / Twilight Cove）发货闭环。  
**详细交接见 [`项目说明.md`](项目说明.md)**；上服务器见 [`部署_固定IP清单.md`](部署_固定IP清单.md)。

## 职责

1. **认渠道**：待处理有渠道则保留（无渠道 → 人工在赛狐指派）  
2. **物流下单**：`applyTrackNo` 推三方仓（昇新→金猫 WMS，BLACKCAT→黑猫 WMS）  
3. **闭环**：WMS 已发货+运单 → 称重或快速出库回传赛狐  

本地状态：`NEW → CHANNEL_ASSIGNED → ORDERED → CLOSED`（另有 `FAILED` / `STALE`）。

## 本机常用

```powershell
cd E:\project\海外仓\sellfox-bridge
.\status_bridge.ps1          # 看常驻
.\start_bridge.ps1 / .\stop_bridge.ps1
.\run_recon_now.ps1          # 手跑对账
python main.py --config config\config.g2-3shops.yaml --dry-run --once
```

生产常驻配置：`config/config.g2-3shops.yaml`（含密钥，勿提交）。

## 灰度回顾

1. dry-run → G1 单店认渠道 → G2 自动下单 → 三店扩量（已验收）  
2. 与 automation：三店 G2 运行时勿双开真跑  
