# 固定 IP 部署清单（sellfox-bridge）

> 更新：2026-07-22  
> 目标：把三店 G2 从「本机家宽」迁到 **固定出口 IP** 机器，减少 40005、支持稳定日清。  
> 推荐目标机：WMS 同机或同网段 **`193.112.93.60`**（或任意固定公网 IP 的 Windows/Linux 服务器）。

---

## 0. 为什么要迁

| 本机家宽 | 固定 IP 服务器 |
|---|---|
| 出口 IP 会变 → 赛狐 40005 | 白名单加一次即可 |
| 需登录才跑计划任务 | 可 7×24 / 开机自启 |
| 适合调试 | 适合生产日清 |

本机 Win 自启可作过渡；**正式日清以本清单为准**。

---

## 1. 部署前准备

- [ ] 确认目标机 OS（Windows Server / Windows 10+ / Linux）
- [ ] 确认目标机 **出网能访问**：
  - `https://openapi.sellfox.com`
  - `http://193.112.93.60:9999`（若 bridge 与 WMS 同机，可用 `127.0.0.1:9999` 并改 config）
  - `https://open.feishu.cn`（飞书）
- [ ] 在目标机测公网出口 IP（**直连、不走代理**）：

```powershell
# Windows 示例（与 bridge 一样 trust_env 直连）
python -c "import requests; s=requests.Session(); s.trust_env=False; print(s.get('http://myip.ipip.net',timeout=10).text)"
```

- [ ] 将该 **出口 IP** 加入赛狐开放平台 IP 白名单（与 client_id=368233 对应）
- [ ] 本机/旧环境：知悉迁完后停本机 G2，避免双实例双下单

---

## 2. 拷贝与环境

### 2.1 建议目录

| OS | 路径示例 |
|---|---|
| Windows | `D:\apps\sellfox-bridge` 或 `C:\services\sellfox-bridge` |
| Linux | `/opt/sellfox-bridge` |

### 2.2 需要拷贝的内容

```
main.py, recon.py, requirements.txt
bridge/          （整个包）
config/
  config.example.yaml
  config.g2-3shops.yaml   # 或部署后现写，含密钥
run_g2_3shops_service.bat / install_*.ps1   # Win
（可选）项目说明.md、部署_固定IP清单.md
```

**不要**依赖拷贝本机 `bridge.db`（可空库重来；或只迁未闭环 ORDERED 时再评估）。  
**不要**把密钥提交 git；用 U 盘/加密通道拷 `config.g2-3shops.yaml`。

### 2.3 Python

- Windows：Python **3.12**，勾选 Add to PATH  
- 安装依赖：

```powershell
cd D:\apps\sellfox-bridge
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 3. 配置检查（`config/config.g2-3shops.yaml`）

- [ ] `sellfox.client_id` / `client_secret`
- [ ] `wms.base_url`（同机可改为 `http://127.0.0.1:9999`）
- [ ] `wms.profiles.jinmao` + `blackcat` 的 key/secret
- [ ] `run.shop_whitelist`: `["396706","398202","398203"]`
- [ ] `run.auto_apply_track_no: true`
- [ ] `notify.feishu_webhook`（生产告警）
- [ ] `ship_confirm_mode: auto`

联调：

```powershell
python main.py --config config/config.g2-3shops.yaml --dry-run --once
# 期望：token OK、无 40005、能拉到待处理或 0 条
python recon.py --config config/config.g2-3shops.yaml --days 1 --limit 5
```

---

## 4. 常驻（按 OS 二选一）

### 4.1 Windows（与本机相同套路）

1. 改 `run_g2_3shops_service.bat` 内 `PYEXE` 为服务器 Python 路径  
2. 改 `install_autostart.ps1` 若需要「开机不论登录」：

生产更稳选项（需管理员 + 保存密码）：

- 触发器：**启动时**（AtStartup）  
- 主体：**不管用户是否登录都运行**  
- 使用有权限的服务账号  

或使用 **NSSM** 注册为服务（见下）。

```powershell
# 在项目目录
powershell -ExecutionPolicy Bypass -File .\install_autostart.ps1
Start-ScheduledTask -TaskName SellfoxBridge-G2-3shops
.\status_bridge.ps1
```

每日对账：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_recon_daily.ps1
# 时间默认 08:07，可按服务器时区调整
```

**NSSM 要点（可选）：**

| 项 | 值 |
|---|---|
| Path | `...\python.exe` |
| Arguments | `main.py --config config\config.g2-3shops.yaml` |
| Startup directory | 项目根 |
| Restart | 自动 |

### 4.2 Linux systemd

见历史说明摘要：

```ini
[Service]
WorkingDirectory=/opt/sellfox-bridge
ExecStart=/usr/bin/python3 main.py --config config/config.g2-3shops.yaml
Restart=always
RestartSec=10
```

```bash
sudo systemctl enable --now sellfox-bridge
```

recon：cron 例如 `7 8 * * * cd /opt/sellfox-bridge && python3 recon.py --config config/config.g2-3shops.yaml --days 7 >> logs/recon.log 2>&1`

---

## 5. 切换上线当天

1. [ ] 服务器 dry-run / once 正常  
2. [ ] **停本机** G2：`.\stop_bridge.ps1` + `.\uninstall_autostart.ps1`（避免双开）  
3. [ ] 启服务器常驻  
4. [ ] 飞书应能收到测试或后续失败告警  
5. [ ] 观察 1～2 小时：下单、WMS 入账、闭环  
6. [ ] 确认三店 **无** automation 真跑双开  
7. [ ] （可选）网页/automation 保留一周仅回退  

---

## 6. 回滚

| 场景 | 动作 |
|---|---|
| 服务器异常 | 停服务器进程；本机 `install_autostart` + start（并确认 IP 白名单含本机） |
| 误双开 | 立刻停其中一侧；已下单的单在赛狐/WMS 跟业务，不能靠停进程撤销 |
| 只读观察 | 两端都停真下单，改 `--dry-run` 或 `auto_apply_track_no: false` |

---

## 7. 验收标准

- [ ] 连续 ≥1 个工作日无 40005  
- [ ] 三店均有自动下单进正确 WMS（jinmao/blackcat）  
- [ ] 出库单能 `CLOSED`  
- [ ] 每日 recon 有日志；high 有飞书或人工查阅  
- [ ] 本机不再跑生产 G2  

---

## 8. 安全

- 配置含密钥与 webhook → 目录权限收紧；勿提交 git  
- 服务器勿开无关代理导致出口 IP 漂移  
- 赛狐 client 保持 `trust_env=False`（代码已设）  

---

## 9. 相关文件

| 文件 | 说明 |
|---|---|
| `项目说明.md` | 业务与现行运行方式 |
| `config/config.g2-3shops.yaml` | 生产配置模板（密钥本机已填） |
| `install_autostart.ps1` / `install_recon_daily.ps1` | Win 自启与日对账 |
| `灰度_G2_三店.md` | 扩店说明 |
