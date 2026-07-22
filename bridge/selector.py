"""渠道决策引擎：目的国 + 预估计费重 → 最优渠道（性价比/可用性）。

第一期价卡在 config.yaml 本地维护；渠道停用状态启动时用
queryShipChannel 同步一次（enabled 且赛狐侧 status=1 才可用）。
"""
import logging

log = logging.getLogger(__name__)


class NoChannelError(Exception):
    """无可用渠道——转人工"""


class ChannelSelector:
    def __init__(self, channels_cfg, sku_weights):
        self.channels = channels_cfg
        self.sku_weights = sku_weights  # {sku: 克重}

    def sync_sellfox_status(self, sellfox_channels):
        """用赛狐"查询物流渠道列表"结果刷新渠道可用状态。
        sellfox_channels: ShipChannelOpenVO 列表"""
        status_by_id = {
            c["providerAuthDetailId"]: c["status"] for c in (sellfox_channels or [])
        }
        for ch in self.channels:
            sf = status_by_id.get(ch["sellfox_provider_auth_detail_id"])
            if sf == 0 and ch.get("enabled"):
                log.warning("渠道 %s 在赛狐侧已停用，本地同步停用", ch["name"])
                ch["enabled"] = False

    def estimate_weight_g(self, items):
        """按 SKU 档案预估包裹总重（g）。缺档案的 SKU 返回 None 转人工。"""
        total = 0
        for it in items:
            sku = it.get("commoditySku") or it.get("sellerSku")
            qty = int(it.get("quantityOrdered") or 1)
            w = self.sku_weights.get(sku)
            if w is None:
                log.warning("SKU %s 无预估重量档案", sku)
                return None
            total += w * qty
        return total

    def select(self, country_code, weight_g):
        """返回最优渠道 dict；无可用渠道抛 NoChannelError。"""
        candidates = []
        for ch in self.channels:
            if not ch.get("enabled"):
                continue
            if country_code not in ch.get("countries", []):
                continue
            if weight_g and ch.get("max_weight_g") and weight_g > ch["max_weight_g"]:
                continue
            cost = ch.get("base_cost", 0) + (
                ch.get("cost_per_kg", 0) * (weight_g or 0) / 1000
            )
            candidates.append((cost, ch))
        if not candidates:
            raise NoChannelError(
                f"目的国={country_code} 重量={weight_g}g 无可用渠道"
            )
        candidates.sort(key=lambda x: x[0])
        cost, best = candidates[0]
        log.info(
            "选渠道: %s (预估运费=%.2f, 候选%d条)", best["name"], cost, len(candidates)
        )
        return best
