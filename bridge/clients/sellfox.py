"""赛狐开放平台客户端：token 缓存 + HMAC-SHA256 签名 + 业务接口封装。

签名规则（doc-1749562）：
  data = 按参数名排序的 "k=v" 用 & 拼接，参数为
         access_token/client_id/method/nonce/timestamp/url（body 不参与签名）
  sign = HmacSHA256(client_secret, data) 的 hex
"""
import hashlib
import hmac
import logging
import random
import time

import requests

log = logging.getLogger(__name__)


class SellfoxError(Exception):
    def __init__(self, code, msg, request_id=None):
        super().__init__(f"sellfox code={code} msg={msg} requestId={request_id}")
        self.code = code
        self.msg = msg


class SellfoxClient:
    def __init__(self, base_url, client_id, client_secret, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self._token = None
        self._token_expire_at = 0  # epoch 秒
        # 直连、不走系统代理：赛狐校验来源IP白名单，走代理会导致出口IP漂移
        self.http = requests.Session()
        self.http.trust_env = False

    # ---- 鉴权 ----

    def _get_token(self):
        now = time.time()
        if self._token and now < self._token_expire_at - 600:  # 提前10分钟刷新
            return self._token
        r = self.http.get(
            f"{self.base_url}/api/oauth/v2/token.json",
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        body = r.json()
        if body.get("code") != 0:
            raise SellfoxError(body.get("code"), body.get("msg"), body.get("requestId"))
        self._token = body["data"]["access_token"]
        self._token_expire_at = now + body["data"]["expires_in"] / 1000
        log.info("sellfox token refreshed, expires_in=%sms", body["data"]["expires_in"])
        return self._token

    def _sign(self, url_path, token, timestamp, nonce):
        params = {
            "url": url_path,
            "method": "post",
            "access_token": token,
            "client_id": self.client_id,
            "timestamp": timestamp,
            "nonce": nonce,
        }
        data = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return hmac.new(
            self.client_secret.encode(), data.encode(), hashlib.sha256
        ).hexdigest()

    def post(self, url_path, body, retries=3):
        """调用业务接口。token 失效自动重取一次；网络错误退避重试。"""
        last_err = None
        for attempt in range(retries):
            token = self._get_token()
            ts = int(time.time() * 1000)
            nonce = random.randint(1, 99999)
            query = {
                "access_token": token,
                "client_id": self.client_id,
                "timestamp": ts,
                "nonce": nonce,
                "sign": self._sign(url_path, token, ts, nonce),
            }
            try:
                r = self.http.post(
                    f"{self.base_url}{url_path}",
                    params=query,
                    json=body,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                r.raise_for_status()
                resp = r.json()
            except (requests.RequestException, ValueError) as e:
                last_err = e
                log.warning("sellfox %s 网络异常(第%d次): %s", url_path, attempt + 1, e)
                time.sleep(2**attempt)
                continue
            code = resp.get("code")
            if code == 0:
                return resp.get("data")
            # token 失效类错误：清缓存重试（具体错误码以公共报错文档 doc-1759053 为准）
            if "token" in str(resp.get("msg", "")).lower() and attempt < retries - 1:
                log.warning("sellfox token 疑似失效，重新获取: %s", resp.get("msg"))
                self._token = None
                continue
            raise SellfoxError(code, resp.get("msg"), resp.get("requestId"))
        raise SellfoxError(-1, f"重试{retries}次仍失败: {last_err}")

    # ---- 业务接口 ----

    def get_package_page(self, status, date_start, date_end, page_no=1,
                         page_size=200, shop_ids=None):
        body = {
            "pageNo": str(page_no),
            "pageSize": str(page_size),
            "packageStatus": status,
            "purchaseDateStart": date_start,
            "purchaseDateEnd": date_end,
        }
        if shop_ids:
            body["shopIdList"] = [str(s) for s in shop_ids]
        return self.post("/api/packageShip/v1/getPackagePage.json", body)

    def warehouse_list(self, page_no=1, page_size=200):
        """仓库列表。type: -1虚拟仓 0默认仓 1国内仓 2FBA仓 3海外仓"""
        return self.post(
            "/api/warehouseManage/warehouseList.json",
            {"pageNo": str(page_no), "pageSize": str(page_size)},
        )

    def query_ship_channels(self, logistics_type="1"):
        """logisticsType: 1=三方仓库物流（WMS 的渠道）"""
        return self.post(
            "/api/packageShip/queryShipChannel.json",
            {"logisticsType": [logistics_type]},
        )

    def update_package_detail(self, package_sns, warehouse_id, is_oversea,
                              provider_auth_detail_id):
        """= 网页上的"更换"仓库/渠道"""
        return self.post(
            "/api/packageShip/updatePackageDetail.json",
            {
                "packageSns": package_sns,
                "warehouseId": warehouse_id,
                "isOversea": is_oversea,
                "providerAuthDetailId": provider_auth_detail_id,
            },
        )

    def apply_track_no(self, package_sns):
        """物流下单：触发赛狐向 WMS（三方仓）推单并申请运单号"""
        return self.post(
            "/api/packageShip/applyTrackNo.json", {"packageSns": package_sns}
        )

    def weighing_shipment(self, items):
        """称重发货。items: [{originalNum, weight, weightUnit}]"""
        return self.post("/api/packageShip/weighingShipment.json", {"items": items})

    def quick_outbound(self, package_list):
        """快速出库（无需重量）。package_list: [{packageSn, carrier, trackNo,
        warehouseId, isOversea, shipmentType}]"""
        return self.post(
            "/api/packageShip/quickOutbound.json", {"packageList": package_list}
        )
