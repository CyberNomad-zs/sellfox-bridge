# -*- coding: utf-8 -*-
"""
sellfox-bridge · 图形启动器（Tkinter，Python 自带，无新依赖）。
仿 automation/gui.py：绿=安全 · 红=真跑 · 蓝=工具
点按钮 → 新控制台窗口执行；真跑需输入 YES 二次确认。

启动：双击「美化启动器.bat」，或  pythonw gui.py / python gui.py
"""
import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import font as tkfont
from tkinter import simpledialog, messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

# 固定 Python 3.12（本机依赖装在此；避免 py -3 落到空环境 3.14）
PY312 = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Programs", "Python", "Python312", "python.exe",
)


def detect_py():
    if os.path.isfile(PY312):
        return f'"{PY312}"'
    if shutil.which("python"):
        return "python"
    if shutil.which("py"):
        return "py -3.12"
    return f'"{sys.executable}"'


PY = detect_py()

# key -> (cmd 模板, 二次确认 key 或 None)
TEMPLATES = {
    "status": (
        "title SF-status&& powershell -NoProfile -ExecutionPolicy Bypass -File status_bridge.ps1&& echo.&& pause",
        None,
    ),
    "dryrun_once": (
        "title SF-dryrun-once&& {PY} main.py --config config\\config.g2-3shops.yaml --dry-run --once&& echo.&& pause",
        None,
    ),
    "dryrun": (
        "title SF-dryrun&& {PY} main.py --config config\\config.g2-3shops.yaml --dry-run",
        None,
    ),
    "start_svc": (
        "title SF-start&& powershell -NoProfile -ExecutionPolicy Bypass -File start_bridge.ps1&& echo.&& pause",
        None,
    ),
    "stop_svc": (
        "title SF-stop&& powershell -NoProfile -ExecutionPolicy Bypass -File stop_bridge.ps1&& echo.&& pause",
        None,
    ),
    "g2_3shops": (
        "title SF-G2-3shops&& {PY} main.py --config config\\config.g2-3shops.yaml",
        "g2_3shops",
    ),
    "g2_agnis": (
        "title SF-G2-Agnis&& {PY} main.py --config config\\config.g2-agnis.yaml",
        "g2_agnis",
    ),
    "g1_agnis": (
        "title SF-G1-Agnis&& {PY} main.py --config config\\config.g1-agnis.yaml",
        "g1_agnis",
    ),
    "g1_homecove": (
        "title SF-G1-HomeCove&& {PY} main.py --config config\\config.g1-homecove.yaml",
        "g1_homecove",
    ),
    "recon": (
        "title SF-recon&& {PY} recon.py --config config\\config.g2-3shops.yaml --days 7&& echo.&& pause",
        None,
    ),
    "recon_now": (
        "title SF-recon-now&& powershell -NoProfile -ExecutionPolicy Bypass -File run_recon_now.ps1",
        None,
    ),
    "install_auto": (
        "title SF-install-auto&& powershell -NoProfile -ExecutionPolicy Bypass -File install_autostart.ps1&& echo.&& pause",
        None,
    ),
    "install_recon": (
        "title SF-install-recon&& powershell -NoProfile -ExecutionPolicy Bypass -File install_recon_daily.ps1&& echo.&& pause",
        None,
    ),
    "uninstall_auto": (
        "title SF-uninstall-auto&& powershell -NoProfile -ExecutionPolicy Bypass -File uninstall_autostart.ps1&& echo.&& pause",
        None,
    ),
    "deps": (
        "title SF-deps&& {PY} -m pip install -r requirements.txt -i " + PIP_MIRROR + "&& echo.&& pause",
        None,
    ),
    "feishu": (
        "title SF-feishu&& {PY} -c \"import yaml;from bridge.notify import Notifier;\n"
        "c=yaml.safe_load(open(r'config/config.g2-3shops.yaml',encoding='utf-8'));\n"
        "n=Notifier(c.get('notify',{}).get('feishu_webhook',''), c.get('customer',{}).get('name','test'));\n"
        "n.warn('飞书连通测试 OK（来自美化启动器）');\n"
        "print('done')\"&& echo.&& pause",
        None,
    ),
}

CONFIRM_MSG = {
    "g2_3shops": (
        "【三店 G2 真跑】Agnis + HomeCove + Twilight Cove\n"
        "将真实调用赛狐「物流下单」并可能回传平台。\n"
        "请确认：未同时开 automation 三店真跑；仅一个 bridge 实例。"
    ),
    "g2_agnis": (
        "【仅 Agnis G2 真跑】将真实物流下单（applyTrackNo）。\n"
        "请确认未与其它 bridge / automation 双开。"
    ),
    "g1_agnis": (
        "【仅 Agnis G1】推进本地 CHANNEL_ASSIGNED，默认不下单\n"
        "（auto_apply_track_no 在 g1 配置中为 false）。"
    ),
    "g1_homecove": (
        "【仅 HomeCove G1】推进本地状态，默认不下单。"
    ),
}


def build_inner(key):
    tmpl, _ = TEMPLATES[key]
    return tmpl.format(PY=PY)


def launch_console(inner):
    subprocess.Popen(
        f'cmd /k "{inner}"',
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=BASE_DIR,
    )


class App:
    def __init__(self, root):
        self.root = root
        root.title("sellfox-bridge · 启动器")
        root.configure(bg="#f4f6f8")
        root.minsize(460, 640)
        try:
            root.tk.call("tk", "scaling", 1.15)
        except Exception:
            pass

        self.f_title = tkfont.Font(family="Microsoft YaHei UI", size=15, weight="bold")
        self.f_sub = tkfont.Font(family="Microsoft YaHei UI", size=9)
        self.f_sec = tkfont.Font(family="Microsoft YaHei UI", size=10, weight="bold")
        self.f_btn = tkfont.Font(family="Microsoft YaHei UI", size=11)
        self.f_status = tkfont.Font(family="Microsoft YaHei UI", size=9)

        head = tk.Frame(root, bg="#1f6feb")
        head.pack(fill="x")
        tk.Label(
            head, text="赛狐 ↔ WMS · sellfox-bridge",
            bg="#1f6feb", fg="white", font=self.f_title,
        ).pack(anchor="w", padx=16, pady=(12, 0))
        tk.Label(
            head,
            text="绿=安全/只读 · 红=真跑(下单/回传) · 蓝=工具　　点按钮在新窗口运行",
            bg="#1f6feb", fg="#d7e6ff", font=self.f_sub,
        ).pack(anchor="w", padx=16, pady=(2, 12))

        body = tk.Frame(root, bg="#f4f6f8")
        body.pack(fill="both", expand=True, padx=14, pady=10)

        s0 = self._section(body, "① 状态 / 常驻（计划任务）")
        self._btn(s0, "查看状态", "safe", lambda: self.handle("status"), col=0,
                  hint="任务+进程+日志尾")
        self._btn(s0, "启动常驻 G2", "safe", lambda: self.handle("start_svc"), col=1,
                  hint="三店日清（计划任务）")
        self._btn(s0, "停止 bridge", "neutral", lambda: self.handle("stop_svc"),
                  full=True, hint="停任务+结束 main.py")

        s1 = self._section(body, "② 核对（安全，第一次先跑）")
        self._btn(s1, "dry-run 一轮", "safe", lambda: self.handle("dryrun_once"), col=0,
                  hint="只读拉单，退出")
        self._btn(s1, "dry-run 常驻", "safe", lambda: self.handle("dryrun"), col=1,
                  hint="只读循环 Ctrl+C 停")

        s2 = self._section(body, "③ 真跑（不可逆 · 需 YES）")
        self._btn(s2, "三店 G2 · 真跑", "danger", lambda: self.handle("g2_3shops"),
                  full=True, hint="生产：下单+回传 · 推荐")
        self._btn(s2, "仅 Agnis G2", "danger", lambda: self.handle("g2_agnis"), col=0,
                  hint="单店真下单")
        self._btn(s2, "仅 Agnis G1", "danger", lambda: self.handle("g1_agnis"), col=1,
                  hint="认渠道·默认不下单")
        self._btn(s2, "仅 HomeCove G1", "danger", lambda: self.handle("g1_homecove"),
                  full=True, hint="认渠道·默认不下单")

        s3 = self._section(body, "④ 对账 / 运维")
        self._btn(s3, "对账一轮", "tool", lambda: self.handle("recon"), col=0,
                  hint="近7天 has_shipped")
        self._btn(s3, "对账+看日志", "tool", lambda: self.handle("recon_now"), col=1,
                  hint="run_recon_now.ps1")
        self._btn(s3, "安装登录自启", "tool", lambda: self.handle("install_auto"), col=0)
        self._btn(s3, "安装每日对账", "tool", lambda: self.handle("install_recon"), col=1)
        self._btn(s3, "取消登录自启", "tool", lambda: self.handle("uninstall_auto"),
                  full=True)

        s4 = self._section(body, "⑤ 工具")
        self._btn(s4, "打开日志文件夹", "tool", lambda: self.handle("logs"), col=0)
        self._btn(s4, "安装依赖", "tool", lambda: self.handle("deps"), col=1)
        self._btn(s4, "测试飞书", "tool", lambda: self.handle("feishu"), full=True)

        self.status = tk.StringVar(value="就绪　·　" + BASE_DIR)
        tk.Label(
            root, textvariable=self.status, bg="#e9edf1", fg="#444",
            font=self.f_status, anchor="w",
        ).pack(fill="x", side="bottom", ipady=4)

    def _section(self, parent, title):
        wrap = tk.Frame(parent, bg="#f4f6f8")
        wrap.pack(fill="x", pady=(4, 8))
        tk.Label(
            wrap, text=title, bg="#f4f6f8", fg="#333",
            font=self.f_sec, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        grid = tk.Frame(wrap, bg="#f4f6f8")
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1, uniform="c")
        grid.columnconfigure(1, weight=1, uniform="c")
        grid._row = 0
        grid._col = 0
        return grid

    _COLORS = {
        "safe": ("#2e9e5b", "#268a4f"),
        "danger": ("#d64545", "#c23b3b"),
        "tool": ("#3b7dd8", "#356fc2"),
        "neutral": ("#6b7280", "#5c626b"),
    }

    def _btn(self, grid, text, kind, cmd, col=None, full=False, hint=None):
        bg, abg = self._COLORS[kind]
        label = text if not hint else f"{text}\n{hint}"
        b = tk.Button(
            grid, text=label, command=cmd, bg=bg, fg="white",
            activebackground=abg, activeforeground="white",
            font=self.f_btn, relief="flat", bd=0, cursor="hand2",
            justify="center", pady=8,
        )
        if full:
            b.grid(row=grid._row, column=0, columnspan=2, sticky="ew", padx=3, pady=3)
            grid._row += 1
            grid._col = 0
        else:
            c = grid._col if col is None else col
            b.grid(row=grid._row, column=c, sticky="ew", padx=3, pady=3)
            if c == 1:
                grid._row += 1
                grid._col = 0
            else:
                grid._col = 1

    def handle(self, key):
        if key == "logs":
            os.makedirs(LOG_DIR, exist_ok=True)
            try:
                os.startfile(LOG_DIR)
                # also try open project root for bridge.log
                os.startfile(BASE_DIR)
            except Exception as e:
                messagebox.showerror("打开失败", str(e))
            self.status.set("已打开日志 / 项目目录")
            return

        if key not in TEMPLATES:
            messagebox.showerror("未知操作", key)
            return

        confirm_key = TEMPLATES[key][1]
        if confirm_key:
            if not self._confirm_real(CONFIRM_MSG[confirm_key]):
                self.status.set("已取消（未确认 YES）")
                return
        launch_console(build_inner(key))
        self.status.set(f"已在新窗口启动：{key}")

    def _confirm_real(self, desc):
        v = simpledialog.askstring(
            "二次确认 · 真实操作",
            desc + "\n\n以上可能产生真实下单/回传。\n确认请输入大写  YES  ：",
            parent=self.root,
        )
        return (v or "").strip() == "YES"


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
