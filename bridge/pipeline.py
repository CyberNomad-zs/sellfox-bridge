"""包裹处理流水线：每轮做四步，均幂等（本地状态 + 赛狐包裹状态双确认）。

step1_discover : 拉赛狐 to_process 包裹 → 本地 NEW（FAILED 有渠道可复活）
step2_assign   : NEW → 选渠道/保留 → CHANNEL_ASSIGNED；陈旧 NEW → STALE
step3_order    : CHANNEL_ASSIGNED → applyTrackNo（推 WMS）→ ORDERED
step4_close    : ORDERED → 查 WMS 出库状态 → 称重发货/快速出库 → CLOSED
"""
import datetime
import logging
import time

from . import store as st
from .clients.wms import WmsError
from .selector import NoChannelError

log = logging.getLogger(__name__)

# WMS orderStatus（Constants.java 实测确认）：0待发货 1预发货 2已发货 4平台已发货
# 注意：状态=2 但运单未生成的情况存在，闭环需同时满足"状态已发货 + 运单号存在"
WMS_SHIPPED_STATUSES = {"2", "4"}


class Pipeline:
    def __init__(self, cfg, sellfox, wms, selector, store, notifier, dry_run=False):
        self.cfg = cfg
        self.sf = sellfox
        # wms: WmsClient 或 {profile_name: WmsClient}（双客户：jinmao/blackcat）
        if isinstance(wms, dict):
            self.wms_clients = wms
            self.wms = next(iter(wms.values()))  # 兼容旧代码引用 self.wms
        else:
            self.wms_clients = {"default": wms}
            self.wms = wms
        self.selector = selector
        self.store = store
        self.notify = notifier
        self.dry_run = dry_run

    def _run_cfg(self):
        return self.cfg.get("run") or {}

    def _wms_for_channel(self, channel_name):
        """按渠道配置的 wms_profile 选 WMS 客户端；未配置时按名称猜 BLACKCAT→blackcat。"""
        ch = self._match_existing_channel(channel_name) or {}
        profile = ch.get("wms_profile")
        if not profile:
            # 兜底：渠道名含 BLACKCAT → blackcat，否则 default_profile / 唯一客户端
            if channel_name and "BLACKCAT" in str(channel_name).upper():
                profile = "blackcat"
            else:
                profile = (self.cfg.get("wms") or {}).get("default_profile")
        if profile and profile in self.wms_clients:
            return self.wms_clients[profile], profile
        # 再退：default_profile 或任意一个
        default = (self.cfg.get("wms") or {}).get("default_profile")
        if default and default in self.wms_clients:
            return self.wms_clients[default], default
        name = next(iter(self.wms_clients))
        return self.wms_clients[name], name

    def _shop_allowed(self, shop_id):
        """灰度白名单：run.shop_whitelist 非空时只处理列表内店铺（step2/3/4 均过滤）。"""
        wl = self.cfg.get("run", {}).get("shop_whitelist") or []
        if not wl:
            return True
        return str(shop_id or "") in {str(x) for x in wl}

    def _rows_for_step(self, state):
        """by_state + 店铺白名单过滤（单店灰度安全网）。"""
        rows = []
        skipped = 0
        for row in self.store.by_state(state):
            if self._shop_allowed(row["shop_id"] if "shop_id" in row.keys() else None):
                rows.append(row)
            else:
                skipped += 1
        if skipped:
            log.info(
                "白名单过滤: state=%s 跳过其它店铺 %d 条，本批处理 %d 条",
                state, skipped, len(rows),
            )
        return rows

    def _match_existing_channel(self, channel_name):
        """包裹已带渠道时（channelName 形如 昇新海外仓-BLACKCAT-RM，
        取后缀匹配 config 渠道名），返回配置项或 None"""
        for ch in self.cfg["channels"]:
            if channel_name and channel_name.endswith(ch["name"]):
                return ch
        return None

    def _pkg_channel(self, pkg):
        return ((pkg.get("logistics") or {}).get("channelName") or "")

    def _date_window(self):
        days = self.cfg["run"]["purchase_date_days"]
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=days)
        return (
            start.strftime("%Y-%m-%d %H:%M:%S"),
            end.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _iter_package_pages(self, status, max_pages=20):
        """分页拉赛狐包裹；status 如 to_process / apply_track_no / has_shipped。"""
        date_start, date_end = self._date_window()
        shop_ids = self.cfg["run"]["shop_whitelist"] or None
        page_no = 1
        while page_no <= max_pages:
            data = self.sf.get_package_page(
                status, date_start, date_end,
                page_no=page_no, shop_ids=shop_ids,
            )
            rows = (data or {}).get("rows") or []
            for p in rows:
                yield p
            if page_no >= (data or {}).get("totalPage", 1) or not rows:
                break
            page_no += 1

    # ---- step 1: 发现新包裹 ----

    def step1_discover(self):
        found, seen, revived = 0, 0, 0
        # 每轮重建缓存：已入库的单也要带明细，否则 step2 会因 cache miss 永久跳过
        self._package_cache = {}
        for p in self._iter_package_pages("to_process"):
            seen += 1
            sn = p["packageSn"]
            order_id = (p.get("orders") or [{}])[0].get("amazonOrderId", "")
            country = (p.get("address") or {}).get("countryCode", "")
            shop_id = p.get("shopId")
            # 无论是否新单，都缓存明细供本轮 step2 使用
            self._package_cache[sn] = p
            if self.store.upsert_new(sn, shop_id, order_id, country):
                found += 1
                continue
            # A1: FAILED/STALE 且本轮仍在 to_process → 条件复活
            row = self.store.get(sn)
            if not row:
                continue
            state = row["state"]
            if state not in (st.FAILED, st.STALE):
                continue
            ch_name = self._pkg_channel(p)
            existing = self._match_existing_channel(ch_name)
            if existing and existing.get("enabled"):
                # 有可用渠道：复活为 NEW，本轮 step2 会推进
                self.store.revive_to_new(
                    sn, shop_id=shop_id, order_id=order_id, country=country
                )
                revived += 1
                log.info(
                    "%s %s→NEW 复活（赛狐已有渠道 %s）",
                    sn, state, existing["name"],
                )
            elif state == st.STALE:
                # 仍无渠道但回到待处理：给人工一次机会
                self.store.revive_to_new(
                    sn, shop_id=shop_id, order_id=order_id, country=country
                )
                revived += 1
                log.info("%s STALE→NEW 复活（回到待处理，仍无渠道）", sn)
            # FAILED + 仍无渠道：保持 FAILED，避免每轮重复告警
        log.info(
            "step1: 赛狐待处理 %d 条，其中新入库 %d 条，复活 %d 条",
            seen, found, revived,
        )
        return found

    def step1b_sync_ordered(self):
        """A3 幂等：赛狐已是 apply_track_no 的包裹，本地同步为 ORDERED，
        避免对已下单包裹再次 applyTrackNo。"""
        synced = 0
        # 可同步为 ORDERED 的本地状态（尚未推仓成功标记的）
        syncable = {st.NEW, st.CHANNEL_ASSIGNED, st.FAILED, st.STALE}
        # 只拉 apply_track_no（物流下单中）：体量小，足够防重复 applyTrackNo。
        # has_shipped 量大，不做全量扫；已 ORDERED 的由 step4 跟闭环。
        try:
            pages = list(self._iter_package_pages("apply_track_no", max_pages=15))
        except Exception as e:
            # 赛狐偶发对 apply_track_no 返回 400（空列表/参数），不阻断本轮
            log.warning("step1b 拉 apply_track_no 失败（本轮跳过同步）: %s", e)
            pages = []
        for p in pages:
            sn = p.get("packageSn")
            if not sn or not self._shop_allowed(p.get("shopId")):
                continue
            row = self.store.get(sn)
            if not row:
                order_id = (p.get("orders") or [{}])[0].get("amazonOrderId", "")
                country = (p.get("address") or {}).get("countryCode", "")
                self.store.upsert_new(sn, p.get("shopId"), order_id, country)
                row = self.store.get(sn)
            if not row or row["state"] not in syncable:
                continue
            ch = self._match_existing_channel(self._pkg_channel(p))
            fields = {}
            if ch:
                fields["channel_name"] = ch["name"]
            track = ((p.get("logistics") or {}).get("trackNo")
                     or (p.get("logistics") or {}).get("trackingNumber"))
            if track:
                fields["track_no"] = track
            prev = row["state"]
            self.store.set_state(sn, st.ORDERED, **fields)
            synced += 1
            log.info(
                "%s %s→ORDERED 同步（赛狐 apply_track_no 渠道=%s）",
                sn, prev, fields.get("channel_name") or row["channel_name"],
            )
        if synced:
            log.info("step1b: 自赛狐 apply_track_no 同步 ORDERED %d 条", synced)
        return synced

    # ---- step 2: 选渠道 + 指派 ----

    def step2_assign(self):
        keep = self.cfg["run"].get("keep_existing_channel", True)
        stale_days = int(self._run_cfg().get("stale_new_days", 3))
        stale_sec = max(stale_days, 0) * 86400
        now = int(time.time())
        for row in self._rows_for_step(st.NEW):
            sn = row["package_sn"]
            pkg = self._package_cache.get(sn)
            if pkg is None:
                # A2: 陈旧 NEW — 超过 stale_new_days 且本轮不在 to_process → STALE
                updated = int(row["updated_at"] or row["created_at"] or 0)
                if stale_sec and updated and (now - updated) >= stale_sec:
                    self.store.mark_stale(sn, f"{stale_days}天不在to_process")
                    log.info(
                        "%s NEW→STALE（%d 天未在待处理，停止刷日志）",
                        sn, stale_days,
                    )
                else:
                    log.debug(
                        "%s 跳过：本轮未拉到包裹明细，保留 NEW",
                        sn,
                    )
                continue
            try:
                weight = self.selector.estimate_weight_g(pkg.get("items", []))
                existing = self._match_existing_channel(self._pkg_channel(pkg))
                if keep and existing and existing.get("enabled"):
                    # 赛狐已配好渠道且可用：不动，直接进入待下单
                    if self.dry_run:
                        wms_p = existing.get("wms_profile") or "?"
                        log.info(
                            "[dry-run] %s 保留已有渠道 %s (wms_profile=%s)",
                            sn, existing["name"], wms_p,
                        )
                        continue
                    self.store.set_state(
                        sn, st.CHANNEL_ASSIGNED,
                        channel_name=existing["name"], weight_g=weight,
                    )
                    log.info(
                        "%s 保留已有渠道 %s → CHANNEL_ASSIGNED (未调写接口)",
                        sn, existing["name"],
                    )
                    continue
                # 无渠道/渠道停用：业务已定人工指派，不自动 selector（缺重量则 FAILED）
                if weight is None:
                    raise NoChannelError("SKU 缺重量档案（无渠道请人工在赛狐指派）")
                country = row["country"] or self.cfg["run"].get("default_country", "")
                ch = self.selector.select(country, weight)
                if self.dry_run:
                    log.info("[dry-run] %s → 渠道 %s (%dg)", sn, ch["name"], weight)
                    continue
                self.sf.update_package_detail(
                    [sn],
                    ch["warehouse_id"],
                    self.cfg["warehouse"]["is_oversea"],
                    ch["sellfox_provider_auth_detail_id"],
                )
                self.store.set_state(
                    sn, st.CHANNEL_ASSIGNED, channel_name=ch["name"], weight_g=weight
                )
                log.info("%s 已指派渠道 %s (updatePackageDetail)", sn, ch["name"])
            except NoChannelError as e:
                self.store.mark_failed(sn, e)
                self.notify.warn(f"包裹 {sn} 无法选渠道: {e}，请人工处理")
            except Exception as e:
                log.exception("step2 %s 失败", sn)
                self.store.mark_failed(sn, e)
                self.notify.warn(f"包裹 {sn} 指派渠道失败: {e}")

    # ---- step 3: 物流下单（推送 WMS）----

    def step3_order(self):
        if not self.cfg["run"]["auto_apply_track_no"]:
            return
        rows = self._rows_for_step(st.CHANNEL_ASSIGNED)
        if not rows:
            return
        # 可选：只对指定渠道名自动下单（G2 可先只放开部分渠道）
        allow_suffixes = self.cfg.get("run", {}).get("order_channel_names") or []
        if allow_suffixes:
            allow_set = {str(x) for x in allow_suffixes}
            filtered = []
            for r in rows:
                chn = r["channel_name"] if "channel_name" in r.keys() else None
                if chn and str(chn) in allow_set:
                    filtered.append(r)
                else:
                    log.info(
                        "%s 跳过物流下单：渠道=%s 不在 order_channel_names=%s",
                        r["package_sn"], chn, sorted(allow_set),
                    )
            rows = filtered
            if not rows:
                return
        sns = [r["package_sn"] for r in rows][:200]  # 接口单次上限200
        if self.dry_run:
            log.info("[dry-run] 物流下单: %s", sns)
            return
        log.info("step3 物流下单(真写) 共 %d 单: %s", len(sns), sns)
        result = self.sf.apply_track_no(sns) or {}
        log.info("step3 applyTrackNo 返回: %s", result)
        if not isinstance(result, dict):
            log.warning("step3 applyTrackNo 返回非 dict: %s", type(result))
            return

        def _item_sn(item):
            """successData/failData 元素可能是 str 包裹号，或 {packageSn, msg} dict。"""
            if isinstance(item, str):
                return item, None
            if isinstance(item, dict):
                return item.get("packageSn") or item.get("package_sn"), item.get("msg")
            return None, None

        for item in result.get("successData") or []:
            sn, _ = _item_sn(item)
            if sn:
                self.store.set_state(sn, st.ORDERED)
                log.info("%s 物流下单成功 → ORDERED", sn)
        for item in result.get("failData") or []:
            sn, msg = _item_sn(item)
            if not sn:
                continue
            msg_s = str(msg or "")
            # A3: 赛狐提示已下单/重复 → 视为已 ORDERED，不进 FAILED
            if any(k in msg_s for k in (
                "已下单", "已经下单", "重复", "已申请", "无需重复", "已交运",
            )):
                self.store.set_state(sn, st.ORDERED)
                log.info("%s 物流下单返回已处理类失败，同步 ORDERED: %s", sn, msg_s)
                continue
            self.store.mark_failed(sn, msg or "物流下单失败")
            self.notify.warn(f"包裹 {sn} 物流下单失败: {msg}")
        # 仅有 success/fail 计数、无明细时：若 success>0 且请求单数=1，可保守标 ORDERED
        if not result.get("successData") and not result.get("failData"):
            sc = result.get("success")
            if sc and int(sc) == len(sns) and len(sns) == 1:
                self.store.set_state(sns[0], st.ORDERED)
                log.info("%s 物流下单 success=%s 无明细，单票按成功 → ORDERED", sns[0], sc)
            else:
                log.warning(
                    "step3 applyTrackNo 无 successData/failData，不自动改状态。"
                    "请到赛狐核对是否已下单: %s | raw=%s",
                    sns, result,
                )
                self.notify.warn(
                    f"物流下单返回无明细，已请求 {sns}，请人工在赛狐核对"
                )

    # ---- step 4: WMS 出库确认 + 回传闭环 ----

    def _resolve_ship_weight_kg(self, row, sn):
        """返回 (weight_kg or None, source)。None 表示应用 quick 兜底。"""
        wg = row["weight_g"] if "weight_g" in row.keys() else None
        if wg:
            return float(wg) / 1000.0, "store"
        # 尝试用本轮缓存或已无法缓存时的 sku 估重（ORDERED 时缓存可能没有）
        pkg = self._package_cache.get(sn)
        if pkg:
            est = self.selector.estimate_weight_g(pkg.get("items", []))
            if est:
                return float(est) / 1000.0, "sku_weights"
        return None, None

    def _ship_confirm_mode(self, has_weight):
        mode = (self._run_cfg().get("ship_confirm_mode") or "weighing").lower()
        if mode == "auto":
            return "weighing" if has_weight else "quick"
        if mode == "quick":
            return "quick"
        # weighing：无重量时仍允许 auto 式降级到 quick，避免 0kg 硬刚
        if mode == "weighing" and not has_weight:
            if self._run_cfg().get("weighing_fallback_quick", True):
                return "quick"
        return mode

    def step4_close(self):
        max_fail = int(self._run_cfg().get("step4_fail_alert_after", 5))
        if not hasattr(self, "_step4_fail_counts"):
            self._step4_fail_counts = {}
        for row in self._rows_for_step(st.ORDERED):
            sn = row["package_sn"]
            try:
                # 按渠道选 WMS 账本：昇新→jinmao，BLACKCAT→blackcat
                wms, wms_profile = self._wms_for_channel(row["channel_name"] or "")
                try:
                    status = wms.query_order_status(sn) or {}
                except WmsError as e:
                    # 刚下单推仓有延迟 / 尚未入账：下轮再查，不算回传失败
                    if any(k in str(e) for k in ("未查询", "不存在", "no order")):
                        log.debug("%s WMS[%s] 暂无单: %s", sn, wms_profile, e)
                        continue
                    raise
                value = str(status.get("orderStatus", ""))
                if value not in WMS_SHIPPED_STATUSES:
                    continue  # 未出库，下一轮再查
                # 双条件：状态已发货 且 运单号已生成
                try:
                    tn = wms.query_tracking_number(sn) or {}
                except WmsError as e:
                    if any(k in str(e) for k in ("未生成", "未查询", "请稍后")):
                        continue
                    raise
                except Exception:
                    continue  # 运单未生成，下一轮再查
                track = tn.get("trackingNumber")
                if not track:
                    continue
                # A4: 运单号尽早回填本地（即使后续回传失败也留痕）
                if not (row["track_no"] if "track_no" in row.keys() else None):
                    self.store.set_state(sn, st.ORDERED, track_no=track)

                # 渠道一致性校验：赛狐为基准
                ch = self._match_existing_channel(row["channel_name"]) or {}
                expected = str(ch.get("expected_carrier", "")).upper()
                actual = str(tn.get("express", "")).upper()
                if (self.cfg["run"].get("hold_on_channel_mismatch", True)
                        and expected and actual and expected not in actual):
                    self.notify.warn(
                        f"包裹 {sn} 渠道不一致：赛狐指派 {row['channel_name']}"
                        f"（应走 {expected}），WMS[{wms_profile}] 实际渠道 {tn.get('express')}"
                        f"（运单 {track}）。已暂停回传，"
                        f"请在 WMS 调整为赛狐渠道后自动恢复"
                    )
                    continue
                if self.dry_run:
                    log.info(
                        "[dry-run] %s WMS[%s] 已出库(运单%s)，应回传赛狐",
                        sn, wms_profile, track,
                    )
                    continue

                weight_kg, wsrc = self._resolve_ship_weight_kg(row, sn)
                mode = self._ship_confirm_mode(has_weight=bool(weight_kg))
                if mode == "quick":
                    self.sf.quick_outbound([{
                        "packageSn": sn,
                        "carrier": tn.get("express", ""),
                        "trackNo": track,
                        "warehouseId": ch.get("warehouse_id"),
                        "isOversea": 3,
                        "shipmentType": 1,
                    }])
                    log.info("%s 快速出库回传 (wms=%s, track=%s)", sn, wms_profile, track)
                else:
                    self.sf.weighing_shipment([{
                        "originalNum": sn,
                        "weight": weight_kg,
                        "weightUnit": "kg",
                    }])
                    log.info(
                        "%s 称重发货回传 weight=%.3fkg src=%s (wms=%s)",
                        sn, weight_kg, wsrc, wms_profile,
                    )
                self.store.set_state(sn, st.CLOSED, track_no=track)
                self._step4_fail_counts.pop(sn, None)
                # 成功只写日志，不推飞书（避免日清刷群）；失败/不一致仍 notify.warn
                log.info("包裹 %s 发货闭环完成 (wms=%s, track=%s)", sn, wms_profile, track)
            except Exception as e:
                log.exception("step4 %s 失败", sn)
                n = self._step4_fail_counts.get(sn, 0) + 1
                self._step4_fail_counts[sn] = n
                if n >= max_fail:
                    self.notify.warn(
                        f"包裹 {sn} 发货回传连续失败 {n} 次: {e}（未置 FAILED，仍可下轮重试）"
                    )
                    self._step4_fail_counts[sn] = 0  # 重置，避免刷屏
                else:
                    self.notify.warn(f"包裹 {sn} 发货回传失败({n}/{max_fail}): {e}")
                # 不置 FAILED，回传失败可下一轮重试

    # ---- 主入口 ----

    _package_cache = {}

    def run_once(self):
        self.step1_discover()
        self.step1b_sync_ordered()  # A3: 赛狐已下单 → 本地 ORDERED
        self.step2_assign()
        self.step3_order()
        self.step4_close()
