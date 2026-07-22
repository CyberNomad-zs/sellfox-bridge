"""WMS 对客户开放接口客户端。

鉴权（各 remote 接口统一，已实测验证 2026-07-15）：
  key       = wms_user_account_info.id
  timestamp = 秒级时间戳（服务端校验 ±300s）
  sign      = MD5(key + api_secret + timestamp) 的【大写】hex
              （服务端 Common.MD5 返回大写并区分大小写比对）
返回结构：{"success": bool, "message": str, "systemCode": int, "data": ...}
  data 可能是 JSON 字符串（服务端 JSONArray.toString），需二次解析。
"""
import hashlib
import json
import logging
import time

import requests

log = logging.getLogger(__name__)


class WmsError(Exception):
    pass


class WmsClient:
    def __init__(self, base_url, key, api_secret, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.key = int(key)
        self.api_secret = api_secret
        self.timeout = timeout
        self.http = requests.Session()
        self.http.trust_env = False  # 直连，不走系统代理

    def _post(self, path, extra=None):
        ts = int(time.time())
        body = {
            "key": self.key,
            "timestamp": ts,
            "sign": hashlib.md5(
                f"{self.key}{self.api_secret}{ts}".encode()
            ).hexdigest().upper(),
        }
        body.update(extra or {})
        r = self.http.post(f"{self.base_url}{path}", json=body, timeout=self.timeout)
        r.raise_for_status()
        resp = r.json()
        if not resp.get("success"):
            raise WmsError(f"wms {path}: {resp.get('message')} (systemCode={resp.get('systemCode')})")
        data = resp.get("data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                pass  # 非 JSON 字符串则原样返回
        return data

    def query_order_status(self, platform_order_no):
        """出库单状态。platformOrderNo 与赛狐包裹的对应关系以联调为准"""
        return self._post(
            "/orderInfo/remote/queryOrderStatus.html",
            {"platformOrderNo": platform_order_no},
        )

    def query_tracking_number(self, platform_order_no):
        """返回含 express / trackingNumber"""
        return self._post(
            "/orderInfo/remote/queryTrackingNumber.html",
            {"platformOrderNo": platform_order_no},
        )

    def query_inventory(self, page=None, size=None):
        """客户库存列表：[{code(sku), num, boxNum, name}]"""
        extra = {}
        if page is not None:
            extra.update({"page": page, "size": size})
        return self._post("/customer/remoteQueryInventory.html", extra)

    def query_product_info(self, page=None, size=None):
        extra = {}
        if page is not None:
            extra.update({"page": page, "size": size})
        return self._post("/customer/remoteQueryProductInfo.html", extra)
