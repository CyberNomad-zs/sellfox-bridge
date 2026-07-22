"""sellfox-bridge 入口：常驻循环。

用法：
  python main.py            # 常驻
  python main.py --once     # 跑一轮退出
  python main.py --dry-run  # 只读演练，不调任何写接口
"""
import argparse
import logging
import sys
import time

import yaml

from bridge.clients.sellfox import SellfoxClient
from bridge.clients.wms import WmsClient
from bridge.notify import Notifier
from bridge.pipeline import Pipeline
from bridge.selector import ChannelSelector
from bridge.store import Store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bridge.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("main")


def build_wms_clients(cfg):
    """构建 WMS 客户端字典 {profile_name: WmsClient}。

    支持两种 config：
      新：wms.profiles.{name}.{key,api_secret} + wms.base_url
      旧：wms.key + wms.api_secret（视为 default_profile 或 'default'）
    """
    wms_cfg = cfg["wms"]
    base = wms_cfg["base_url"]
    clients = {}
    profiles = wms_cfg.get("profiles")
    if profiles:
        for name, p in profiles.items():
            clients[name] = WmsClient(base, p["key"], p["api_secret"])
            log.info("WMS profile=%s key=%s", name, p["key"])
    elif wms_cfg.get("key") is not None and wms_cfg.get("api_secret"):
        # 兼容旧单客户配置
        name = wms_cfg.get("default_profile") or "default"
        clients[name] = WmsClient(base, wms_cfg["key"], wms_cfg["api_secret"])
        log.info("WMS profile=%s key=%s (legacy flat config)", name, wms_cfg["key"])
    else:
        raise ValueError("config.wms 需配置 profiles 或 key+api_secret")
    return clients


def build(cfg, dry_run):
    sellfox = SellfoxClient(
        cfg["sellfox"]["base_url"],
        cfg["sellfox"]["client_id"],
        cfg["sellfox"]["client_secret"],
    )
    wms_clients = build_wms_clients(cfg)
    selector = ChannelSelector(cfg["channels"], cfg.get("sku_weights") or {})
    notifier = Notifier(
        cfg["notify"].get("feishu_webhook", ""), cfg["customer"]["name"]
    )
    store = Store()
    # 启动时用赛狐渠道列表同步一次可用状态
    try:
        selector.sync_sellfox_status(sellfox.query_ship_channels())
    except Exception as e:
        log.warning("启动同步赛狐渠道状态失败（不阻塞）: %s", e)
    return Pipeline(
        cfg, sellfox, wms_clients, selector, store, notifier, dry_run=dry_run
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    pipeline = build(cfg, args.dry_run)
    interval = cfg["run"]["poll_interval_sec"]
    log.info(
        "sellfox-bridge 启动 customer=%s dry_run=%s interval=%ss",
        cfg["customer"]["name"], args.dry_run, interval,
    )
    round_no = 0
    while True:
        round_no += 1
        t0 = time.time()
        log.info("----- 第 %d 轮开始 -----", round_no)
        try:
            pipeline.run_once()
            log.info("----- 第 %d 轮结束，耗时 %.1fs -----", round_no, time.time() - t0)
        except Exception:
            log.exception("本轮执行异常，%ss 后继续", interval)
        if args.once:
            break
        log.info("等待 %ss 后进入下一轮（期间无输出属正常）…", interval)
        time.sleep(interval)


if __name__ == "__main__":
    main()
