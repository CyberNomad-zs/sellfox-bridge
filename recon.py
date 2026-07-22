"""对账脚本（只读）：赛狐已发货包裹 ↔ WMS 运单号逐单核对，差异/漏提交/渠道不一致告警。

背景（见 项目说明.md §6 / 对齐记录_业务语义.md）：
  - 近 N 天赛狐 has_shipped，白名单店铺，逐单按渠道选 WMS 账本核对运单/承运商；
  - 昇新渠道 → jinmao（金猫 key）；BLACKCAT → blackcat（黑猫 key）；
  - 顺带查「赛狐已发货但无 submitTime」的漏提交单。

【只读】只调查询类接口，可安全常跑/定时。

用法：
  python recon.py --config config/config.g2-agnis.yaml
  python recon.py --days 3 --limit 50
  python recon.py --probe
  python recon.py --selftest
  python recon.py --json recon_out.json
"""
import argparse
import json
import logging
import sys

import yaml

from bridge.clients.sellfox import SellfoxClient, SellfoxError
from bridge.clients.wms import WmsClient, WmsError
from bridge.notify import Notifier
from main import build_wms_clients

log = logging.getLogger("recon")

SELLFOX_SHIPPED_STATUS = "has_shipped"
WMS_SHIPPED_STATUSES = {"2", "4"}

SF_TRACKING_PATHS = [
    "logistics.trackingNo", "logistics.trackNo", "trackingNo",
    "trackNo", "trackingNumber", "logistics.trackingNumber",
]
SF_SUBMIT_PATHS = [
    "submitTime", "submitDate", "platformSubmitTime", "orders.0.submitTime",
]
SF_CHANNEL_PATHS = [
    "logistics.channelName", "channelName", "logistics.shipChannelName",
]
SF_CARRIER_PATHS = [
    "logistics.carrier", "carrier", "logistics.providerName",
    "logistics.logisticsName",
]


def _dig(obj, path):
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _first(obj, paths):
    for p in paths:
        v = _dig(obj, p)
        if v not in (None, ""):
            return v
    return None


def extract_sellfox_fields(pkg):
    return {
        "sn": pkg.get("packageSn"),
        "channel_name": _first(pkg, SF_CHANNEL_PATHS),
        "carrier": _first(pkg, SF_CARRIER_PATHS),
        "tracking": _first(pkg, SF_TRACKING_PATHS),
        "submit_time": _first(pkg, SF_SUBMIT_PATHS),
        "country": _dig(pkg, "address.countryCode"),
        "shop_id": pkg.get("shopId"),
    }


def match_channel(channels, channel_name):
    if not channel_name:
        return None
    for ch in channels:
        if channel_name.endswith(ch["name"]):
            return ch
    return None


def wms_profile_for_channel(cfg, channel):
    """渠道 → WMS profile 名（与 pipeline._wms_for_channel 一致）。"""
    if channel and channel.get("wms_profile"):
        return channel["wms_profile"]
    name = (channel or {}).get("name") or ""
    if "BLACKCAT" in str(name).upper():
        return "blackcat"
    return (cfg.get("wms") or {}).get("default_profile") or "jinmao"


def _norm(s):
    return str(s or "").strip().upper()


def classify(sf, channel, wms_tracking, wms_status, wms_error, wms_profile=None):
    """返回 (severity, code, detail)。

    双 WMS 后：BLACKCAT 应查 blackcat profile。
    若在正确账本仍查无 → high；若错误地只在金猫查无，旧逻辑会误报——调用方必须选对 client。
    """
    sn = sf["sn"]
    is_blackcat = bool(channel and str(channel["name"]).upper().startswith("BLACKCAT"))
    is_shengxin = bool(channel and not is_blackcat)

    if wms_error and (
        "未查询" in wms_error or "no order" in wms_error.lower() or "不存在" in wms_error
    ):
        if is_blackcat:
            return (
                "high",
                "WMS_MISSING_BLACKCAT",
                f"{sn} BLACKCAT 渠道但黑猫 WMS({wms_profile}) 查无此单——疑似未推仓/漏账，需核查",
            )
        if is_shengxin:
            return (
                "high",
                "WMS_MISSING",
                f"{sn} 昇新渠道但 WMS({wms_profile}) 查无此单——疑似未过账/漏推，需人工核查",
            )
        return (
            "medium",
            "WMS_MISSING_UNKNOWN_CH",
            f"{sn} 渠道未知({sf['channel_name']})且 WMS 查无，需人工核查",
        )
    if wms_error:
        return ("medium", "WMS_QUERY_ERROR", f"{sn} WMS 查询异常：{wms_error}")

    tn = (wms_tracking or {}).get("trackingNumber")
    express = (wms_tracking or {}).get("express")

    if not tn:
        if wms_status is not None and str(wms_status) not in WMS_SHIPPED_STATUSES:
            return (
                "medium",
                "WMS_NOT_SHIPPED",
                f"{sn} 赛狐已发货，但 WMS 状态={wms_status}（未出库）且无运单号",
            )
        return (
            "medium",
            "WMS_NO_TRACKING",
            f"{sn} 赛狐已发货，WMS 有单但运单号未生成",
        )

    if channel:
        expected = _norm(channel.get("expected_carrier"))
        actual = _norm(express)
        if expected and actual and expected not in actual:
            return (
                "high",
                "CARRIER_MISMATCH",
                f"{sn} 渠道不一致：赛狐 {channel['name']}（应走 {expected}），"
                f"WMS 实际 {express}（运单 {tn}）",
            )

    sf_tn = sf.get("tracking")
    if sf_tn and _norm(sf_tn) != _norm(tn):
        return (
            "high",
            "TRACKING_MISMATCH",
            f"{sn} 双边运单号不一致：赛狐 {sf_tn} ≠ WMS {tn}（承运 {express}）",
        )

    if not sf.get("submit_time"):
        return (
            "medium",
            "SELLFOX_NOT_SUBMITTED",
            f"{sn} 赛狐已发货但无 submitTime——疑似漏提交平台",
        )

    return ("ok", "OK", f"{sn} 一致（运单 {tn} / {express} / wms={wms_profile}）")


def _iter_shipped_packages(sf, cfg, days, limit):
    import datetime

    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=days)
    page_no, yielded = 1, 0
    while True:
        data = sf.get_package_page(
            SELLFOX_SHIPPED_STATUS,
            start.strftime("%Y-%m-%d %H:%M:%S"),
            end.strftime("%Y-%m-%d %H:%M:%S"),
            page_no=page_no,
            shop_ids=cfg["run"].get("shop_whitelist") or None,
        ) or {}
        for p in data.get("rows", []):
            yield p
            yielded += 1
            if limit and yielded >= limit:
                return
        if page_no >= data.get("totalPage", 1):
            return
        page_no += 1


def recon_once(cfg, sf, wms_clients, limit=0):
    """wms_clients: {profile: WmsClient} 或单个 WmsClient（兼容）。"""
    if not isinstance(wms_clients, dict):
        wms_clients = {"default": wms_clients}
    channels = cfg["channels"]
    results = []
    for pkg in _iter_shipped_packages(
        sf, cfg, cfg["run"].get("purchase_date_days", 7), limit
    ):
        s = extract_sellfox_fields(pkg)
        if not s["sn"]:
            continue
        channel = match_channel(channels, s["channel_name"])
        profile = wms_profile_for_channel(cfg, channel)
        wms = wms_clients.get(profile) or next(iter(wms_clients.values()))
        wms_tracking, wms_status, wms_error = None, None, None
        try:
            wms_tracking = wms.query_tracking_number(s["sn"]) or {}
        except WmsError as e:
            wms_error = str(e)
        except Exception as e:
            wms_error = f"{type(e).__name__}: {e}"
        if wms_error is None and not (wms_tracking or {}).get("trackingNumber"):
            try:
                st = wms.query_order_status(s["sn"]) or {}
                wms_status = str(st.get("orderStatus", ""))
            except Exception:
                pass
        severity, code, detail = classify(
            s, channel, wms_tracking, wms_status, wms_error, wms_profile=profile
        )
        results.append({
            "sn": s["sn"],
            "severity": severity,
            "code": code,
            "detail": detail,
            "channel": (channel or {}).get("name") or s["channel_name"],
            "wms_profile": profile,
            "sf_tracking": s["tracking"],
            "wms_tracking": (wms_tracking or {}).get("trackingNumber"),
            "wms_express": (wms_tracking or {}).get("express"),
        })
    summary = {}
    for r in results:
        summary[r["code"]] = summary.get(r["code"], 0) + 1
    return results, summary


def _probe(sf, cfg):
    for i, pkg in enumerate(
        _iter_shipped_packages(
            sf, cfg, cfg["run"].get("purchase_date_days", 7), limit=3
        )
    ):
        print(f"\n===== 已发货包裹样本 #{i + 1} 顶层字段 =====")
        print("keys:", sorted(pkg.keys()))
        for k in ("logistics", "address", "orders"):
            v = pkg.get(k)
            if isinstance(v, dict):
                print(f"{k}.keys:", sorted(v.keys()))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                print(f"{k}[0].keys:", sorted(v[0].keys()))
        print("提取结果:", extract_sellfox_fields(pkg))
    print(
        "\n若 tracking/submit_time/channel 为 None，请据真实 keys 调整 recon.py 顶部 *_PATHS。"
    )


def _selftest():
    ch_sx = {
        "name": "昇新海外仓-DPD",
        "expected_carrier": "DPD",
        "wms_profile": "jinmao",
    }
    ch_bc = {
        "name": "BLACKCAT-EH",
        "expected_carrier": "EH",
        "wms_profile": "blackcat",
    }
    cases = [
        (
            "一致-昇新",
            {"sn": "P1", "channel_name": "昇新海外仓-DPD", "tracking": "T1", "submit_time": "x"},
            ch_sx,
            {"trackingNumber": "T1", "express": "DPD"},
            None,
            None,
            "jinmao",
            "OK",
            "ok",
        ),
        (
            "一致-BLACKCAT黑猫账本",
            {"sn": "P1b", "channel_name": "昇新海外仓-BLACKCAT-EH", "tracking": "T1b", "submit_time": "x"},
            ch_bc,
            {"trackingNumber": "T1b", "express": "EH"},
            None,
            None,
            "blackcat",
            "OK",
            "ok",
        ),
        (
            "承运商不一致",
            {"sn": "P2", "channel_name": "昇新海外仓-DPD", "tracking": "T2", "submit_time": "x"},
            ch_sx,
            {"trackingNumber": "T2", "express": "RM"},
            None,
            None,
            "jinmao",
            "CARRIER_MISMATCH",
            "high",
        ),
        (
            "昇新 WMS 查无",
            {"sn": "P4", "channel_name": "昇新海外仓-DPD", "tracking": None, "submit_time": "x"},
            ch_sx,
            None,
            None,
            "未查询到订单",
            "jinmao",
            "WMS_MISSING",
            "high",
        ),
        (
            "BLACKCAT 黑猫账本查无(异常)",
            {"sn": "P5", "channel_name": "昇新海外仓-BLACKCAT-EH", "tracking": None, "submit_time": "x"},
            ch_bc,
            None,
            None,
            "未查询到订单",
            "blackcat",
            "WMS_MISSING_BLACKCAT",
            "high",
        ),
        (
            "WMS 有单无运单",
            {"sn": "P6", "channel_name": "昇新海外仓-DPD", "tracking": None, "submit_time": "x"},
            ch_sx,
            {"trackingNumber": "", "express": ""},
            "2",
            None,
            "jinmao",
            "WMS_NO_TRACKING",
            "medium",
        ),
        (
            "漏提交",
            {"sn": "P8", "channel_name": "昇新海外仓-DPD", "tracking": "T8", "submit_time": None},
            ch_sx,
            {"trackingNumber": "T8", "express": "DPD"},
            None,
            None,
            "jinmao",
            "SELLFOX_NOT_SUBMITTED",
            "medium",
        ),
    ]
    ok = 0
    for desc, sf, ch, wt, ws, we, prof, exp_code, exp_sev in cases:
        sev, code, detail = classify(sf, ch, wt, ws, we, wms_profile=prof)
        good = code == exp_code and sev == exp_sev
        ok += good
        print(
            f"[{'OK' if good else 'X '}] {desc}: got {sev}/{code}  期望 {exp_sev}/{exp_code}"
        )
        if not good:
            print(f"      detail={detail}")
    # profile helper
    assert wms_profile_for_channel({"wms": {"default_profile": "jinmao"}}, ch_bc) == "blackcat"
    assert wms_profile_for_channel({"wms": {"default_profile": "jinmao"}}, ch_sx) == "jinmao"
    print(f"\n自测 {ok}/{len(cases)} 通过")
    return ok == len(cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("recon.log", encoding="utf-8"),
        ],
    )

    if args.selftest:
        sys.exit(0 if _selftest() else 1)

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if args.days is not None:
        cfg["run"]["purchase_date_days"] = args.days

    sf = SellfoxClient(
        cfg["sellfox"]["base_url"],
        cfg["sellfox"]["client_id"],
        cfg["sellfox"]["client_secret"],
    )
    wms_clients = build_wms_clients(cfg)
    notifier = Notifier(
        cfg["notify"].get("feishu_webhook", ""), cfg["customer"]["name"]
    )

    try:
        if args.probe:
            _probe(sf, cfg)
            return
        log.info(
            "对账开始：近 %s 天已发货，白名单=%s，WMS profiles=%s",
            cfg["run"]["purchase_date_days"],
            cfg["run"].get("shop_whitelist") or "全部",
            list(wms_clients.keys()),
        )
        results, summary = recon_once(cfg, sf, wms_clients, limit=args.limit)
    except SellfoxError as e:
        log.error("赛狐接口失败：%s", e)
        if getattr(e, "code", None) == 40005 or "40005" in str(e):
            log.error(
                "→ 出口 IP 不在赛狐白名单。请在固定 IP/WMS 服务器跑，或加白。"
            )
        sys.exit(2)

    total = len(results)
    anomalies = [r for r in results if r["severity"] in ("high", "medium")]
    highs = [r for r in results if r["severity"] == "high"]
    log.info("对账完成：共 %d 单。分类：%s", total, summary)
    for r in anomalies:
        lvl = log.error if r["severity"] == "high" else log.warning
        lvl("[%s] %s", r["code"], r["detail"])

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(
                {"summary": summary, "results": results},
                f,
                ensure_ascii=False,
                indent=2,
            )
        log.info("结果已写入 %s", args.json)

    if highs:
        lines = "\n".join(f"· {r['detail']}" for r in highs[:20])
        more = f"\n…另有 {len(highs) - 20} 条 high" if len(highs) > 20 else ""
        notifier.warn(
            f"⚠️ 对账发现 {len(highs)} 条严重异常"
            f"（近 {cfg['run']['purchase_date_days']} 天 {total} 单）：\n{lines}{more}"
        )
    elif anomalies:
        notifier.warn(
            f"对账：{total} 单中 {len(anomalies)} 条需关注。统计：{summary}"
        )
    else:
        log.info("对账：全部一致，无异常。")


if __name__ == "__main__":
    main()
