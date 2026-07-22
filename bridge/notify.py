"""告警：飞书群机器人 webhook；未配置时仅写日志。"""
import logging

import requests

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, feishu_webhook="", customer_name=""):
        self.webhook = (feishu_webhook or "").strip()
        self.prefix = f"[sellfox-bridge/{customer_name}] " if customer_name else ""
        # 直连飞书，避免系统代理干扰
        self._http = requests.Session()
        self._http.trust_env = False

    def _send(self, text):
        if not self.webhook:
            return False
        try:
            r = self._http.post(
                self.webhook,
                json={"msg_type": "text", "content": {"text": self.prefix + text}},
                timeout=10,
            )
            if r.status_code != 200:
                log.error("飞书 HTTP %s: %s", r.status_code, (r.text or "")[:200])
                return False
            try:
                body = r.json()
            except Exception:
                return True
            # 自定义机器人成功多为 {"StatusCode":0,...} 或 {"code":0,...}
            code = body.get("code")
            status = body.get("StatusCode", body.get("statusCode"))
            if code not in (None, 0) or (status is not None and status != 0):
                log.error("飞书业务失败: %s", body)
                return False
            return True
        except Exception as e:
            log.error("飞书发送失败: %s", e)
            return False

    def warn(self, text):
        log.warning("ALERT: %s", text)
        self._send(text)

    def info(self, text):
        """一般信息：默认只写日志，不推飞书（降噪）。需要推群用 warn。"""
        log.info("NOTIFY: %s", text)
