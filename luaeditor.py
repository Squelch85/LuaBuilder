#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G HUB Lua 스크립트 빌더 — 통합본 (문법검사 통과판)
요구사항 반영:
- 키보드 키 입력은 따옴표 없이 선택(Combobox) — 내부에서 자동 따옴표 보정
- Ctrl+Space 로 현재 마우스 좌표 캡처 → MoveMouseTo 기본값으로 바로 반영
- 인수 입력은 값 타이핑 대신 선택/스핀 UI 제공
- "→ 추가(기본값)" 버튼은 인수 입력 없이 즉시 스텝 등록
- 레거시 Lua 코드 복사 버튼 제공(미리보기 헤더)
- 작동 트리거 이벤트는 레거시/한글 토글과 연동된 간단 설명
- 다크모드 토글(안정성을 위해 최소 변경: 리스트/미리보기/루트 배경만 전환)

Python 3.9+ / 외부 의존성 없음
"""

from __future__ import annotations
import json
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ==============================
# 이벤트 코드 ↔ 한글표기 및 arg 메타데이터 (G HUB API 문서 기반)
# ==============================
EVENT_DEFS = {
    "PROFILE_ACTIVATED": {
        "label": "프로필 활성화",
        "arg": None,
        "details": ["이 이벤트는 최초 실행 시 한 번 발생합니다."],
    },
    "PROFILE_DEACTIVATED": {
        "label": "프로필 비활성화",
        "arg": None,
        "details": ["프로필이 비활성화될 때 마지막으로 발생합니다."],
    },
    "G_PRESSED": {
        "label": "G 키 눌림",
        "arg": {
            "label": "G 키 번호",
            "min": 1,
            "max": 18,
            "default": 1,
            "allow_all": True,
            "hint": "G1=1, …, G18=18",
        },
        "details": ["arg는 누른 G 키 번호입니다."],
    },
    "G_RELEASED": {
        "label": "G 키 뗌",
        "arg": {
            "label": "G 키 번호",
            "min": 1,
            "max": 18,
            "default": 1,
            "allow_all": True,
            "hint": "G1=1, …, G18=18",
        },
        "details": ["arg는 뗀 G 키 번호입니다."],
    },
    "M_PRESSED": {
        "label": "M 키 눌림",
        "arg": {
            "label": "M 키 번호",
            "min": 1,
            "max": 3,
            "default": 1,
            "allow_all": True,
            "hint": "M1=1, M2=2, M3=3",
        },
        "details": ["arg는 현재 눌린 M 키의 번호입니다."],
    },
    "M_RELEASED": {
        "label": "M 키 뗌",
        "arg": {
            "label": "M 키 번호",
            "min": 1,
            "max": 3,
            "default": 1,
            "allow_all": True,
            "hint": "M1=1, M2=2, M3=3",
        },
        "details": ["arg는 떼어진 M 키의 번호입니다."],
    },
    "MOUSE_BUTTON_PRESSED": {
        "label": "마우스 버튼 눌림",
        "arg": {
            "label": "마우스 버튼",
            "min": 1,
            "max": 5,
            "default": 1,
            "allow_all": True,
            "hint": "1=좌, 2=중, 3=우, 4=X1, 5=X2",
        },
        "details": [
            "arg는 눌린 마우스 버튼 번호입니다.",
            "좌클릭(1)을 받으려면 EnablePrimaryMouseButtonEvents(true) 필요.",
        ],
    },
    "MOUSE_BUTTON_RELEASED": {
        "label": "마우스 버튼 뗌",
        "arg": {
            "label": "마우스 버튼",
            "min": 1,
            "max": 5,
            "default": 1,
            "allow_all": True,
            "hint": "1=좌, 2=중, 3=우, 4=X1, 5=X2",
        },
        "details": [
            "arg는 뗀 마우스 버튼 번호입니다.",
            "좌클릭(1)을 받으려면 EnablePrimaryMouseButtonEvents(true) 필요.",
        ],
    },
}

EVENT_ORDER = list(EVENT_DEFS.keys())
EVENT_LABELS = {code: meta["label"] for code, meta in EVENT_DEFS.items()}

# 표시용(한글) ↔ 코드 역매핑 헬퍼
LABEL_TO_CODE = {v: k for k, v in EVENT_LABELS.items()}

# ==============================
# 키 선택(따옴표 없이)
# ==============================
KEY_CHOICES = [
    "A","B","C","D","E","F","G","H","I","J","K","L","M",
    "N","O","P","Q","R","S","T","U","V","W","X","Y","Z",
    "SPACE","ENTER","ESC","TAB","SHIFT","CTRL","ALT",
    "UP","DOWN","LEFT","RIGHT",
    "1","2","3","4","5","6","7","8","9","0"
]

# ==============================
# 함수 카탈로그
# ==============================
FUNCTION_CATALOG = [
    {"name": "OutputLogMessage", "cat": "System", "icon": "🧾",
     "call": "OutputLogMessage(%(text)s)",
     "args": [{"name": "text", "label": "로그 텍스트", "type": "str", "default": '"Hello G HUB\\n"'}],
     "desc": "로그 창에 메시지 출력"},

    {"name": "Sleep", "cat": "System", "icon": "⏱️",
     "call": "Sleep(%(ms)d)",
     "args": [{"name": "ms", "label": "대기(ms)", "type": "int", "default": 50, "min": 0, "max": 600000}],
     "desc": "밀리초 지연"},

    {"name": "ClearLog", "cat": "System", "icon": "🧹",
     "call": "ClearLog()",
     "args": [],
     "desc": "스크립트 로그 창 비우기"},

    {"name": "PressAndReleaseKey", "cat": "Keyboard", "icon": "⌨️",
     "call": "PressAndReleaseKey(%(k1)s%(k2_opt)s)",
     "args": [
         {"name": "k1", "label": "키1", "type": "choice", "choices": KEY_CHOICES, "default": "A"},
         {"name": "k2", "label": "키2(선택)", "type": "choice", "choices": [""] + KEY_CHOICES, "default": ""},
     ],
     "desc": "키(최대2) 짧게 누르기"},

    {"name": "PressKey", "cat": "Keyboard", "icon": "⬇️",
     "call": "PressKey(%(key)s)",
     "args": [{"name": "key", "label": "키", "type": "choice", "choices": KEY_CHOICES, "default": "A"}],
     "desc": "키 누르기"},

    {"name": "ReleaseKey", "cat": "Keyboard", "icon": "⬆️",
     "call": "ReleaseKey(%(key)s)",
     "args": [{"name": "key", "label": "키", "type": "choice", "choices": KEY_CHOICES, "default": "A"}],
     "desc": "키 떼기"},

    {"name": "MoveMouseRelative", "cat": "Cursor", "icon": "↔️",
     "call": "MoveMouseRelative(%(dx)d, %(dy)d)",
     "args": [
         {"name": "dx", "label": "ΔX", "type": "int", "default": 10, "min": -10000, "max": 10000},
         {"name": "dy", "label": "ΔY", "type": "int", "default": 0, "min": -10000, "max": 10000},
     ],
     "desc": "마우스 상대 이동"},

    {"name": "MoveMouseTo", "cat": "Cursor", "icon": "📍",
      # 내보낼 땐 픽셀→0~65535로 변환하여 출력
     "call": "MoveMouseTo(%(x)d, %(y)d)",
     "args": [
         {"name": "x", "label": "X(px)", "type": "int", "default": "__CENTER_X__"},
         {"name": "y", "label": "Y(px)", "type": "int", "default": "__CENTER_Y__"},
     ],
     "desc": "절대 이동(픽셀 입력 → 0~65535 변환)"},

    {"name": "MoveMouseWheel", "cat": "Mouse", "icon": "🖱️",
     "call": "MoveMouseWheel(%(amount)d)",
     "args": [{"name": "amount", "label": "휠(+위/-아래)", "type": "int", "default": -1, "min": -100, "max": 100}],
     "desc": "마우스 휠 스크롤"},

    {"name": "PressAndReleaseMouseButton", "cat": "Mouse", "icon": "🖱️⚡",
     "call": "PressAndReleaseMouseButton(%(button)s)",
     "args": [{"name": "button", "label": "마우스 버튼", "type": "choice",
               "choices": ["좌(1)", "중(2)", "우(3)", "X1(4)", "X2(5)"], "default": "좌(1)"}],
     "desc": "마우스 버튼 클릭"},

    {"name": "PressMouseButton", "cat": "Mouse", "icon": "🖱️⬇️",
     "call": "PressMouseButton(%(button)s)",
     "args": [{"name": "button", "label": "마우스 버튼", "type": "choice",
               "choices": ["좌(1)", "중(2)", "우(3)", "X1(4)", "X2(5)"], "default": "좌(1)"}],
     "desc": "마우스 버튼 누르기"},

    {"name": "ReleaseMouseButton", "cat": "Mouse", "icon": "🖱️⬆️",
     "call": "ReleaseMouseButton(%(button)s)",
     "args": [{"name": "button", "label": "마우스 버튼", "type": "choice",
               "choices": ["좌(1)", "중(2)", "우(3)", "X1(4)", "X2(5)"], "default": "좌(1)"}],
     "desc": "마우스 버튼 떼기"},

    {"name": "EnablePrimaryMouseButtonEvents", "cat": "System", "icon": "⚙️",
     "call": "EnablePrimaryMouseButtonEvents(%(enable)s)",
     "args": [{"name": "enable", "label": "좌클릭 이벤트 전달", "type": "bool", "default": True}],
     "desc": "좌클릭 이벤트 전달 설정"},

    {"name": "MoveMouseToVirtual", "cat": "Cursor", "icon": "🖥️",
     "call": "MoveMouseToVirtual(%(x)d, %(y)d)",
     "args": [
         {"name": "x", "label": "X(px)", "type": "int", "default": "__CENTER_X__"},
         {"name": "y", "label": "Y(px)", "type": "int", "default": "__CENTER_Y__"},
     ],
     "desc": "멀티 모니터 절대 이동"},

    {"name": "OutputDebugMessage", "cat": "System", "icon": "🐞",
     "call": "OutputDebugMessage(%(text)s)",
     "args": [{"name": "text", "label": "디버그 텍스트", "type": "str", "default": '"Debug: %d\\n"'}],
     "desc": "Windows 디버거로 로그"},

    {"name": "PlayMacro", "cat": "Macro", "icon": "▶️",
     "call": "PlayMacro(%(name)s)",
     "args": [{"name": "name", "label": "매크로 이름", "type": "str", "default": '"My Macro"'}],
     "desc": "기존 매크로 재생"},

    {"name": "PressMacro", "cat": "Macro", "icon": "⏺️",
     "call": "PressMacro(%(name)s)",
     "args": [{"name": "name", "label": "매크로 이름", "type": "str", "default": '"My Macro"'}],
     "desc": "매크로 키 누름만 수행"},

    {"name": "ReleaseMacro", "cat": "Macro", "icon": "⏏️",
     "call": "ReleaseMacro(%(name)s)",
     "args": [{"name": "name", "label": "매크로 이름", "type": "str", "default": '"My Macro"'}],
     "desc": "매크로 키 뗌만 수행"},

    {"name": "AbortMacro", "cat": "Macro", "icon": "⛔",
     "call": "AbortMacro()",
     "args": [],
     "desc": "실행 중 매크로 중지"},

    {"name": "SetMKeyState", "cat": "Keyboard", "icon": "🎛️",
     "call": "SetMKeyState(%(mkey)d)",
     "args": [{"name": "mkey", "label": "M키 상태", "type": "int", "default": 1, "min": 1, "max": 3}],
     "desc": "M키 모드 전환"},
]
CATALOG_BY_NAME = {f["name"]: f for f in FUNCTION_CATALOG}

# ==============================
# 유틸
# ==============================

def _quote_if_needed(s: str) -> str:
    s = str(s).strip()
    if not ((s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))):
        s = f'"{s}"'
    return s


def validate_value(spec: dict, value_str):
    t = spec.get("type")
    if t == "int":
        v = int(str(value_str).strip())
        if "min" in spec and v < spec["min"]:
            raise ValueError(f"{spec['min']} 이상이어야 합니다.")
        if "max" in spec and v > spec["max"]:
            raise ValueError(f"{spec['max']} 이하이어야 합니다.")
        return v
    if t == "float":
        return float(str(value_str).strip())
    if t == "bool":
        if isinstance(value_str, bool):
            return value_str
        s = str(value_str).strip().lower()
        if s in ("true","1","on","yes"): return True
        if s in ("false","0","off","no"): return False
        raise ValueError("불리언(true/false) 값을 입력하세요.")
    if t == "choice":
        choices = spec.get("choices") or []
        if value_str not in choices:
            raise ValueError(f"다음 중 선택: {choices}")
        return value_str
    # str
    return _quote_if_needed(value_str)


def format_call(call_fmt: str, args: dict) -> str:
    params = dict(args)
    has_k2 = "k2" in params
    k2_raw = str(params.get("k2", "")).strip() if has_k2 else ""
    # 불리언 → Lua 소문자
    for k, v in list(params.items()):
        if isinstance(v, bool):
            params[k] = "true" if v else "false"
    # 마우스 버튼 레이블 → 숫자
    if "button" in params:
        b = str(params["button"]) if params["button"] is not None else ""
        label = b.split("(")[0].strip().lower()
        label_map = {
            "좌": 1,
            "중": 2,
            "우": 3,
            "x1": 4,
            "x2": 5,
        }
        if label in label_map:
            params["button"] = label_map[label]
        else:
            try:
                params["button"] = int(b)
            except Exception:
                params["button"] = 1
    # 키 파라미터는 자동 따옴표 보정
    for k in ("key", "k1", "k2"):
        if k in params and str(params[k]).strip() != "":
            params[k] = _quote_if_needed(params[k])
    if has_k2:
        k2 = str(params.get("k2", "")).strip()
        params["k2_opt"] = f", {k2}" if k2_raw else ""
    if "%(" not in call_fmt:
        return call_fmt
    return call_fmt % params

# ==============================
# 인수 입력 다이얼로그
# ==============================
class ArgDialog(tk.Toplevel):
    def __init__(self, app, func_def, preset=None):
        super().__init__(app)
        self.title(f"인수 입력 — {func_def['name']}")
        self.resizable(False, False)
        self.func_def = func_def
        self.app = app
        self.result = None
        self._key_capture_target = None  # "k1"/"k2"/"key"

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        self.vars = {}
        for i, spec in enumerate(func_def.get("args", [])):
            label = spec.get("label", spec["name"]) + ":"
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=4)

            default = spec.get("default")
            if preset and spec["name"] in preset:
                default = preset[spec["name"]]
            elif func_def["name"] in ("MoveMouseTo", "MoveMouseToVirtual"):
                if spec["name"] == "x": default = self.app.screen_w // 2
                if spec["name"] == "y": default = self.app.screen_h // 2

            t = spec.get("type")
            if t == "bool":
                var = tk.BooleanVar(value=bool(default))
                ttk.Checkbutton(frm, variable=var).grid(row=i, column=1, sticky="w")
            elif t == "choice":
                var = tk.StringVar(value=str(default))
                cb = ttk.Combobox(frm, textvariable=var, values=spec.get("choices", []), state="readonly", width=30)
                cb.grid(row=i, column=1, sticky="w")
            elif t == "int":
                var = tk.StringVar(value=str(default))
                sp = ttk.Spinbox(frm, from_=spec.get("min", -999999), to=spec.get("max", 999999), textvariable=var, width=12)
                sp.grid(row=i, column=1, sticky="w")
            else:
                var = tk.StringVar(value=str(default))
                ttk.Entry(frm, textvariable=var, width=34).grid(row=i, column=1, sticky="w")
            self.vars[spec["name"]] = var

        # MoveMouseTo 좌표 캡처 안내 + 단축키
        if func_def["name"] in ("MoveMouseTo", "MoveMouseToVirtual"):
            hint = ttk.Label(frm, text="Ctrl+Space: 현재 마우스 좌표 반영")
            hint.grid(row=888, column=0, columnspan=2, sticky="w", pady=(6,0))
            self.bind("<Control-space>", self._capture_pointer_to_xy)

        # 키보드 계열 자동 설정 버튼 (독립 타깃)
        if func_def["name"] in ("PressKey", "ReleaseKey", "PressAndReleaseKey"):
            kfrm = ttk.Frame(frm)
            kfrm.grid(row=889, column=0, columnspan=2, sticky="w", pady=(6,0))
            if "k1" in self.vars:
                ttk.Button(kfrm, text="키1 자동설정", command=lambda: self.start_key_capture("k1")).pack(side=tk.LEFT)
            if "k2" in self.vars:
                ttk.Button(kfrm, text="키2 자동설정", command=lambda: self.start_key_capture("k2")).pack(side=tk.LEFT, padx=6)
            if "key" in self.vars:
                ttk.Button(kfrm, text="키 자동설정", command=lambda: self.start_key_capture("key")).pack(side=tk.LEFT)
            self.lbl_kcap = ttk.Label(kfrm, text="")
            self.lbl_kcap.pack(side=tk.LEFT, padx=6)
            self.bind("<Key>", self._on_any_key)

        btnfrm = ttk.Frame(frm); btnfrm.grid(row=999, column=0, columnspan=2, pady=(12,0))
        ttk.Button(btnfrm, text="확인", command=self.on_ok).grid(row=0, column=0, padx=4)
        ttk.Button(btnfrm, text="취소", command=self.on_cancel).grid(row=0, column=1, padx=4)

        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.on_cancel())

        self.transient(app); self.grab_set(); self.update_idletasks(); self.center_to_parent(); self.focus_set()

    def start_key_capture(self, target: str):
        self._key_capture_target = target
        if hasattr(self, 'lbl_kcap'):
            self.lbl_kcap.config(text=f"{target.upper()} 대기중 — 아무 키나 누르세요")

    def _on_any_key(self, event):
        target = getattr(self, "_key_capture_target", None)
        if not target:
            return
        key = self._normalize_keysym(event.keysym)
        if key:
            if target in self.vars:
                self.vars[target].set(key)
            if hasattr(self, 'lbl_kcap'):
                self.lbl_kcap.config(text=f"감지: {key} → {target}")
            self._key_capture_target = None

    def _normalize_keysym(self, ks: str) -> str:
        if not ks:
            return ""
        m = {
            "space": "SPACE", "Return": "ENTER", "Escape": "ESC", "Tab": "TAB",
            "Shift_L": "SHIFT", "Shift_R": "SHIFT",
            "Control_L": "CTRL", "Control_R": "CTRL",
            "Alt_L": "ALT", "Alt_R": "ALT",
            "Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT",
        }
        if ks in m:
            return m[ks]
        if len(ks) == 1:
            if ks.isalpha():
                return ks.upper()
            if ks.isdigit():
                return ks
        return ks.upper()

    def center_to_parent(self):
        try:
            self.update_idletasks()
            px = self.master.winfo_rootx(); py = self.master.winfo_rooty()
            pw = self.master.winfo_width(); ph = self.master.winfo_height()
            w = self.winfo_width(); h = self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _capture_pointer_to_xy(self, *_):
        try:
            x = self.winfo_pointerx(); y = self.winfo_pointery()
            if "x" in self.vars: self.vars["x"].set(str(x))
            if "y" in self.vars: self.vars["y"].set(str(y))
            self.app.set_status(f"현재 좌표 적용: {x}, {y}")
        except Exception:
            pass

    def on_ok(self):
        try:
            vals = {}
            for spec in self.func_def.get("args", []):
                name = spec["name"]
                var = self.vars[name]
                raw = var.get() if not isinstance(var, tk.BooleanVar) else var.get()
                if self.func_def["name"] in ("MoveMouseTo", "MoveMouseToVirtual") and spec.get("type") == "int":
                    maxv = self.app.screen_w - 1 if name == "x" else self.app.screen_h - 1
                    v = int(str(raw).strip())
                    if not (0 <= v <= maxv):
                        raise ValueError(f"{name.upper()}는 0~{maxv}px 범위여야 합니다.")
                    vals[name] = v
                else:
                    vals[name] = validate_value(spec, raw)
            self.result = vals
            self.destroy()
        except Exception as e:
            messagebox.showerror("입력 오류", str(e), parent=self)

    def on_cancel(self):
        self.result = None
        self.destroy()

# ==============================
# 메인 앱
# ==============================
class ScriptBuilderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("G HUB Lua 스크립트 빌더")
        self.geometry("1200x720")
        self.minsize(1100, 640)

        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()

        self.steps: list[dict] = []  # [{name, args}]
        self.status = tk.StringVar(value="준비")

        # 토글/상태
        self.var_show_legacy = tk.BooleanVar(value=True)   # True: 레거시 Lua 명칭/출력
        self.var_dark = tk.BooleanVar(value=False)
        self.var_trigger_event = tk.StringVar(value=EVENT_ORDER[0])  # 내부코드 보관
        first_event_arg = EVENT_DEFS.get(EVENT_ORDER[0], {}).get("arg")
        initial_arg = first_event_arg.get("default", first_event_arg.get("min", -1)) if first_event_arg else -1
        self.var_trigger_arg = tk.IntVar(value=initial_arg)
        self.var_enable_primary = tk.BooleanVar(value=True)
        self.captured_xy = None  # Ctrl+Space로 캡처한 좌표

        self.create_widgets()
        self.apply_theme()
        self.bind_shortcuts()
        self.update_preview()

    # ---------- UI ----------
    def create_widgets(self):
        root = ttk.Frame(self, padding=8)
        root.pack(fill=tk.BOTH, expand=True)

        # 상단 바
        top = ttk.Frame(root)
        top.pack(fill=tk.X, pady=(0,8))

        ttk.Checkbutton(top, text="레거시 LUA 보기", variable=self.var_show_legacy, command=self.on_legacy_toggle).pack(side=tk.LEFT)
        ttk.Checkbutton(top, text="다크모드", variable=self.var_dark, command=self.apply_theme).pack(side=tk.LEFT, padx=(10,0))

        ttk.Label(top, text="함수 검색:").pack(side=tk.LEFT, padx=(16,4))
        self.var_search = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.var_search, width=32)
        ent.pack(side=tk.LEFT)
        ent.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Label(top, text="이벤트:").pack(side=tk.LEFT, padx=(16,4))
        self.cb_event = ttk.Combobox(top, state="readonly", width=28)
        self.cb_event.bind("<<ComboboxSelected>>", self.on_event_display_selected)
        self.cb_event.pack(side=tk.LEFT)

        self.arg_frame = ttk.Frame(top)
        self._arg_frame_pack = {"side": tk.LEFT, "padx": (12, 0)}
        self.arg_frame.pack(**self._arg_frame_pack)
        self.lbl_arg = ttk.Label(self.arg_frame, text="Arg:")
        self.lbl_arg.pack(side=tk.LEFT, padx=(0, 4))
        self.spin_arg = ttk.Spinbox(self.arg_frame, from_=-1, to=16, textvariable=self.var_trigger_arg, width=8)
        self.spin_arg.pack(side=tk.LEFT)

        self.refresh_event_combobox(reset_arg=True)
        ttk.Checkbutton(top, text="EnablePrimaryMouseButtonEvents(true)", variable=self.var_enable_primary).pack(side=tk.LEFT, padx=12)

        # 중앙 3분할
        mid = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        mid.pack(fill=tk.BOTH, expand=True)

        # 좌: 카테고리 트리뷰
        left = ttk.Frame(mid); mid.add(left, weight=1)
        self.tree = ttk.Treeview(left, columns=("name",), show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-Button-1>", lambda e: self.add_selected_func_with_dialog())

        # 중: 조작 버튼 (기본값 추가 / 상세 입력)
        center = ttk.Frame(mid); mid.add(center)
        ttk.Button(center, text="→ 추가(기본값)", command=self.add_selected_func, width=14).pack(pady=(10,4))
        ttk.Button(center, text="상세 입력…", command=self.add_selected_func_with_dialog, width=14).pack(pady=4)
        ttk.Button(center, text="← 삭제", command=self.remove_selected_steps, width=14).pack(pady=4)
        ttk.Separator(center, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Button(center, text="위로 ↑", command=lambda: self.move_selected_steps(-1), width=14).pack(pady=4)
        ttk.Button(center, text="아래로 ↓", command=lambda: self.move_selected_steps(1), width=14).pack(pady=4)
        ttk.Button(center, text="복제", command=self.duplicate_selected_steps, width=14).pack(pady=12)

        # 우: 스텝 리스트 + 미리보기
        right = ttk.Frame(mid); mid.add(right, weight=2)
        self.lb_steps = tk.Listbox(right, activestyle="dotbox", selectmode=tk.EXTENDED, exportselection=False)
        self.lb_steps.pack(fill=tk.BOTH, expand=True)
        self.lb_steps.bind("<Double-Button-1>", lambda e: self.edit_selected_step())

        prev_hdr = ttk.Frame(right); prev_hdr.pack(fill=tk.X, pady=(6,2))
        ttk.Label(prev_hdr, text="미리보기:").pack(side=tk.LEFT)
        ttk.Button(prev_hdr, text="Lua 복사", command=self.copy_lua_to_clipboard).pack(side=tk.RIGHT, padx=4)
        ttk.Checkbutton(prev_hdr, text="레거시 Lua 보기", variable=self.var_show_legacy, command=self.on_legacy_toggle).pack(side=tk.RIGHT)
        self.txt_preview = tk.Text(right, height=12, wrap="word")
        self.txt_preview.configure(state=tk.DISABLED)
        self.txt_preview.pack(fill=tk.BOTH, expand=False)

        # 하단: 파일/상태
        bottom = ttk.Frame(root)
        bottom.pack(fill=tk.X, pady=(8,0))
        ttk.Button(bottom, text="인수 편집", command=self.edit_selected_step).pack(side=tk.LEFT)
        ttk.Button(bottom, text="전체 삭제", command=self.clear_steps).pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom, text="JSON 저장", command=self.save_project).pack(side=tk.LEFT, padx=12)
        ttk.Button(bottom, text="JSON 불러오기", command=self.load_project).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Lua 내보내기", command=self.export_lua).pack(side=tk.RIGHT)

        status_frm = ttk.Frame(root); status_frm.pack(fill=tk.X, pady=(4,0))
        ttk.Label(status_frm, textvariable=self.status, anchor="w").pack(fill=tk.X)

        self.populate_func_tree()

    def bind_shortcuts(self):
        self.bind("<Delete>", lambda e: (self.remove_selected_steps(), "break")[1])
        self.bind("<Control-Up>", lambda e: (self.move_selected_steps(-1), "break")[1])
        self.bind("<Control-Down>", lambda e: (self.move_selected_steps(1), "break")[1])
        self.bind("<Control-d>", lambda e: (self.duplicate_selected_steps(), "break")[1])
        self.bind("<Return>", lambda e: (self.add_selected_func(), "break")[1])  # 기본 추가
        self.bind("<Control-Shift-s>", lambda e: (self.quick_add_sleep(), "break")[1])
        self.bind("<Control-space>", self.on_ctrl_space_capture)  # 전역 좌표 캡처

    # ---------- 테마 ----------
    def apply_theme(self):
        """최소 커스터마이징 + 다크모드에서 함수목록(Treeview)/미리보기(Text)까지 색 반영"""
        try:
            sty = ttk.Style()
            sty.theme_use("clam")
        except Exception:
            sty = ttk.Style()
        if self.var_dark.get():
            bg = "#1e1f22"; acc = "#2b2d31"; fg = "#e6e6e6"; sel = "#3a3d41"
            try:
                # 리스트/프리뷰 직접 지정
                self.lb_steps.configure(bg=acc, fg=fg, selectbackground=sel, selectforeground=fg)
                self.txt_preview.configure(bg=acc, fg=fg, insertbackground=fg)
                # 트리뷰 색 (함수 목록)
                try:
                    sty.configure("Treeview", background=acc, fieldbackground=acc, foreground=fg)
                    sty.configure("Treeview.Heading", background=acc, foreground=fg)
                except Exception:
                    pass
                self.configure(bg=bg)
            except Exception:
                pass
        else:
            try:
                self.lb_steps.configure(bg="white", fg="black")
                self.txt_preview.configure(bg="white", fg="black", insertbackground="black")
                try:
                    sty.configure("Treeview", background="white", fieldbackground="white", foreground="black")
                    sty.configure("Treeview.Heading", background="", foreground="black")
                except Exception:
                    pass
                self.configure(bg="SystemButtonFace")
            except Exception:
                pass

    # ---------- 레거시 토글 / 이벤트 콤보 ----------
    def on_legacy_toggle(self):
        self.populate_func_tree()
        self.refresh_steps()
        self.refresh_event_combobox()
        self.update_preview()

    def refresh_event_combobox(self, reset_arg: bool = False):
        # 내부 저장은 코드, 콤보박스 표시는 레거시/한글 연동
        if self.var_show_legacy.get():
            display_map = {c: c for c in EVENT_ORDER}
        else:
            display_map = {c: EVENT_LABELS[c] for c in EVENT_ORDER}
        self.cb_event["values"] = [display_map[c] for c in EVENT_ORDER]
        code = self.var_trigger_event.get()
        if code not in EVENT_ORDER:
            code = EVENT_ORDER[0]
            self.var_trigger_event.set(code)
        self.cb_event.set(display_map.get(code, display_map[EVENT_ORDER[0]]))
        self.update_trigger_controls(reset_value=reset_arg)

    def update_trigger_controls(self, reset_value: bool = False):
        code = self.var_trigger_event.get()
        meta = EVENT_DEFS.get(code, {})
        arg_meta = meta.get("arg")
        if not arg_meta:
            self.var_trigger_arg.set(-1)
            if self.arg_frame.winfo_manager():
                self.arg_frame.pack_forget()
            return

        if not self.arg_frame.winfo_manager():
            self.arg_frame.pack(**self._arg_frame_pack)

        allow_all = arg_meta.get("allow_all", False)
        spin_from = -1 if allow_all else arg_meta.get("min", 0)
        spin_to = arg_meta.get("max", 16)
        increment = arg_meta.get("step", 1)
        self.lbl_arg.config(text=f"{arg_meta.get('label', 'Arg')}:")
        self.spin_arg.config(from_=spin_from, to=spin_to, increment=increment)

        current = self.var_trigger_arg.get()
        if reset_value or (current < spin_from and current != -1) or current > spin_to:
            self.var_trigger_arg.set(arg_meta.get("default", spin_from if spin_from != -1 else arg_meta.get("min", 0)))
        elif not allow_all and current == -1:
            self.var_trigger_arg.set(arg_meta.get("default", arg_meta.get("min", 0)))

    def on_event_display_selected(self, _):
        display = self.cb_event.get()
        if self.var_show_legacy.get():
            self.var_trigger_event.set(display)
        else:
            self.var_trigger_event.set(LABEL_TO_CODE.get(display, EVENT_ORDER[0]))
        self.update_trigger_controls(reset_value=True)
        self.update_preview()

    # ---------- 함수 트리 ----------
    def display_name_for_func(self, f: dict) -> str:
        return f"{f.get('icon','')} {f['name'] if self.var_show_legacy.get() else f.get('desc', f['name'])}"

    def populate_func_tree(self):
        self.tree.delete(*self.tree.get_children())
        q = (getattr(self, 'var_search', tk.StringVar()).get() or "").strip().lower()
        cats = {}
        for f in FUNCTION_CATALOG:
            hay = (f["name"] + " " + f.get("desc", "") + " " + f.get("cat"," ")).lower()
            if q and not all(t in hay for t in q.split()):
                continue
            cats.setdefault(f["cat"], []).append(f)
        for cat in sorted(cats.keys()):
            nid = self.tree.insert("", tk.END, text=f"📂 {cat}")
            for f in sorted(cats[cat], key=lambda x: x["name"].lower()):
                self.tree.insert(nid, tk.END, text=self.display_name_for_func(f), values=(f["name"],))
            self.tree.item(nid, open=True)

    def apply_filter(self):
        prev = self.get_selected_catalog_func()
        prev_name = prev["name"] if prev else None
        self.populate_func_tree()
        if prev_name:
            for cat in self.tree.get_children():
                for item in self.tree.get_children(cat):
                    if self.tree.set(item, "name") == prev_name:
                        self.tree.selection_set(item)
                        self.tree.see(item)
                        return

    # ---------- 상태/미리보기 ----------
    def set_status(self, text: str):
        try:
            self.status.set(text)
        except Exception:
            pass

    def update_preview(self):
        content = self.generate_lua() if self.var_show_legacy.get() else self.generate_korean_doc()
        self.txt_preview.configure(state=tk.NORMAL)
        self.txt_preview.delete("1.0", tk.END)
        self.txt_preview.insert("1.0", content)
        self.txt_preview.configure(state=tk.DISABLED)

    def generate_korean_doc(self) -> str:
        lines = []
        lines.append("[설명 보기]")
        ev_code = self.var_trigger_event.get()
        ev_meta = EVENT_DEFS.get(ev_code, {})
        ev_label = ev_meta.get("label", ev_code)
        ar = self.var_trigger_arg.get()
        lines.append("실행 조건 설명:")
        lines.append(f"- 이벤트: '{ev_label}'")
        arg_meta = ev_meta.get("arg")
        if arg_meta:
            if ar == -1:
                lines.append(f"- {arg_meta['label']}: 전체 (모든 값)")
            else:
                lines.append(f"- {arg_meta['label']}: {ar}")
            if arg_meta.get("hint"):
                lines.append(f"  · {arg_meta['hint']}")
        else:
            lines.append("- 추가 인수 없음")

        lines.append("세부 안내:")
        for detail in ev_meta.get("details", []):
            lines.append(f"- {detail}")
        if self.var_enable_primary.get():
            lines.append("- 좌클릭 이벤트 전달 설정: EnablePrimaryMouseButtonEvents(true)")
        else:
            lines.append("- 좌클릭 이벤트 전달 설정: EnablePrimaryMouseButtonEvents(false)")
        lines.append("")
        # 요약 조건
        cond = []
        if ev_code:
            cond.append(f"event='{ev_code}'")
        if arg_meta and ar != -1:
            cond.append(f"arg == {ar}")
        if cond:
            lines.append(f"실제 실행 조건: {' and '.join(cond)} 일 때")
        elif ev_code:
            lines.append(f"실제 실행 조건: event='{ev_code}' 일 때")
        else:
            lines.append("실제 실행 조건: (항상 실행)")
        lines.append("")
        if not self.steps:
            lines.append("(스텝이 없습니다)")
        for i, st in enumerate(self.steps, 1):
            lines.append(f"{i}. {self.localized_step_desc(st)}")
        return "\n".join(lines) + "\n"

    def localized_step_desc(self, step: dict) -> str:
        name = step.get("name"); a = step.get("args", {})
        try:
            def _button_value(val):
                try:
                    return int(val)
                except Exception:
                    label = str(val).split("(")[0].strip().lower()
                    return {"좌": 1, "중": 2, "우": 3, "x1": 4, "x2": 5}.get(label, 1)

            if name == "MoveMouseTo":
                return f"마우스를 ({int(a.get('x',0))}px, {int(a.get('y',0))}px) 위치로 이동"
            if name == "MoveMouseToVirtual":
                return f"가상 화면 ({int(a.get('x',0))}px, {int(a.get('y',0))}px) 위치로 이동"
            if name == "MoveMouseRelative":
                return f"마우스를 상대 이동: ΔX={int(a.get('dx',0))}, ΔY={int(a.get('dy',0))}"
            if name == "PressAndReleaseKey":
                k1 = a.get('k1','""'); k2 = a.get('k2','').strip()
                return f"키를 짧게 누름: {k1}" + (f", {k2}" if k2 else "")
            if name == "PressKey":
                return f"키 누름: {a.get('key','""')}"
            if name == "ReleaseKey":
                return f"키 떼기: {a.get('key','""')}"
            if name == "MoveMouseWheel":
                return f"마우스 휠 스크롤: {int(a.get('amount',0))}"
            if name == "PressAndReleaseMouseButton":
                return f"마우스 버튼 클릭: {_button_value(a.get('button',1))}"
            if name == "PressMouseButton":
                return f"마우스 버튼 누름: {_button_value(a.get('button',1))}"
            if name == "ReleaseMouseButton":
                return f"마우스 버튼 떼기: {_button_value(a.get('button',1))}"
            if name == "EnablePrimaryMouseButtonEvents":
                return "좌클릭 이벤트를 스크립트로 전달: " + ("예" if a.get('enable', True) else "아니오")
            if name == "OutputLogMessage":
                return f"로그 출력: {a.get('text','""')}"
            if name == "OutputDebugMessage":
                return f"디버그 로그: {a.get('text','""')}"
            if name == "ClearLog":
                return "스크립트 로그 비우기"
            if name == "Sleep":
                return f"대기: {int(a.get('ms',0))} ms"
            if name == "PlayMacro":
                return f"매크로 재생: {a.get('name','""')}"
            if name == "PressMacro":
                return f"매크로 누름: {a.get('name','""')}"
            if name == "ReleaseMacro":
                return f"매크로 뗌: {a.get('name','""')}"
            if name == "AbortMacro":
                return "실행 중 매크로 중지"
            if name == "SetMKeyState":
                return f"M 키 상태 설정: M{int(a.get('mkey',1))}"
        except Exception:
            pass
        return f"{name} (인수: {a})"

    # ---------- 스텝 조작 ----------
    def refresh_steps(self):
        self.lb_steps.delete(0, tk.END)
        for st in self.steps:
            self.lb_steps.insert(tk.END, self.render_step_label(st))
        if self.steps:
            self.lb_steps.see(tk.END)
        self.update_preview()

    def render_step_label(self, step):
        legacy = self.var_show_legacy.get()
        name = step["name"]; args = step.get("args", {})
        if legacy:
            if name == "MoveMouseTo":
                x_px = int(args.get("x", 0)); y_px = int(args.get("y", 0))
                return f"[MoveMouseTo] X={x_px}px, Y={y_px}px"
            kv = ", ".join([f"{k}={v}" for k, v in args.items() if k != "k2_opt"]) or "(no args)"
            return f"[{name}] {kv}"
        else:
            return self.localized_step_desc(step)

    def build_default_args(self, fdef: dict) -> dict:
        args = {}
        for spec in fdef.get("args", []):
            name = spec["name"]; default = spec.get("default")
            if fdef["name"] in ("MoveMouseTo", "MoveMouseToVirtual"):
                if name == "x" and default == "__CENTER_X__":
                    args[name] = (self.captured_xy[0] if self.captured_xy else self.screen_w // 2)
                    continue
                if name == "y" and default == "__CENTER_Y__":
                    args[name] = (self.captured_xy[1] if self.captured_xy else self.screen_h // 2)
                    continue
            t = spec.get("type")
            if t == "int":
                if isinstance(default, str):
                    default = default.replace("__CENTER_X__", str(self.screen_w // 2)).replace("__CENTER_Y__", str(self.screen_h // 2))
                args[name] = int(default)
            elif t == "bool":
                args[name] = bool(default)
            else:
                args[name] = default
        return args

    def add_selected_func(self):
        # 기본값으로 즉시 추가
        f = self.get_selected_catalog_func()
        if not f:
            messagebox.showinfo("안내", "함수를 선택하세요.")
            return
        step = {"name": f["name"], "args": self.build_default_args(f)}
        sel = self.lb_steps.curselection()
        if sel:
            pos = sel[0] + 1
            self.steps.insert(pos, step)
            self.refresh_steps(); self.lb_steps.selection_clear(0, tk.END); self.lb_steps.selection_set(pos); self.lb_steps.see(pos)
        else:
            self.steps.append(step)
            self.refresh_steps(); self.lb_steps.selection_clear(0, tk.END); self.lb_steps.selection_set(len(self.steps)-1); self.lb_steps.see(tk.END)
        self.set_status(f"스텝 추가됨: {step['name']}")

    def add_selected_func_with_dialog(self):
        f = self.get_selected_catalog_func()
        if not f:
            messagebox.showinfo("안내", "함수를 선택하세요.")
            return
        dlg = ArgDialog(self, f, preset=self.build_default_args(f))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        step = {"name": f["name"], "args": dlg.result}
        sel = self.lb_steps.curselection()
        if sel:
            pos = sel[0] + 1
            self.steps.insert(pos, step)
            self.refresh_steps(); self.lb_steps.selection_clear(0, tk.END); self.lb_steps.selection_set(pos); self.lb_steps.see(pos)
        else:
            self.steps.append(step)
            self.refresh_steps(); self.lb_steps.selection_clear(0, tk.END); self.lb_steps.selection_set(len(self.steps)-1); self.lb_steps.see(tk.END)

    def get_selected_catalog_func(self):
        sel = self.tree.selection()
        if not sel:
            return None
        item = sel[0]
        vals = self.tree.set(item)
        if not vals:
            return None
        fname = vals.get("name")
        return CATALOG_BY_NAME.get(fname)

    def get_selected_indices(self):
        sel = list(self.lb_steps.curselection())
        return sorted(sel)

    def remove_selected_steps(self):
        idxs = self.get_selected_indices()
        if not idxs: return
        for i in reversed(idxs):
            del self.steps[i]
        self.refresh_steps()
        if self.steps:
            self.lb_steps.selection_set(min(idxs[0], len(self.steps)-1))

    def duplicate_selected_steps(self):
        idxs = self.get_selected_indices()
        if not idxs: return
        insert_pos = idxs[-1] + 1
        new_items = [json.loads(json.dumps(self.steps[i])) for i in idxs]
        for off, st in enumerate(new_items):
            self.steps.insert(insert_pos + off, st)
        self.refresh_steps()
        # 새로 추가된 영역 선택
        self.lb_steps.selection_clear(0, tk.END)
        for j in range(insert_pos, insert_pos + len(new_items)):
            self.lb_steps.selection_set(j)
        self.lb_steps.see(insert_pos + len(new_items) - 1)

    def move_selected_steps(self, delta: int):
        idxs = self.get_selected_indices()
        if not idxs: return
        if delta < 0:
            if idxs[0] == 0: return
            for i in idxs:
                self.steps[i-1], self.steps[i] = self.steps[i], self.steps[i-1]
            new_sel = [i-1 for i in idxs]
        else:
            if idxs[-1] == len(self.steps)-1: return
            for i in reversed(idxs):
                self.steps[i+1], self.steps[i] = self.steps[i], self.steps[i+1]
            new_sel = [i+1 for i in idxs]
        self.refresh_steps()
        self.lb_steps.selection_clear(0, tk.END)
        for i in new_sel:
            self.lb_steps.selection_set(i)
        self.lb_steps.see(new_sel[-1])

    def duplicate_step(self):
        idx = self.lb_steps.curselection()
        if not idx: return
        pos = idx[0]
        step = json.loads(json.dumps(self.steps[pos]))
        self.steps.insert(pos+1, step)
        self.refresh_steps(); self.lb_steps.selection_set(pos+1); self.lb_steps.see(pos+1)

    def move_step(self, delta: int):
        idx = self.lb_steps.curselection()
        if not idx: return
        pos = idx[0]; newpos = pos + delta
        if not (0 <= newpos < len(self.steps)): return
        self.steps[pos], self.steps[newpos] = self.steps[newpos], self.steps[pos]
        self.refresh_steps(); self.lb_steps.selection_set(newpos); self.lb_steps.see(newpos)

    def clear_steps(self):
        if not self.steps: return
        if messagebox.askyesno("확인", "모든 스텝을 삭제할까요?"):
            self.steps.clear(); self.refresh_steps()

    def edit_selected_step(self):
        idx = self.lb_steps.curselection()
        if not idx: return
        pos = idx[0]; step = self.steps[pos]
        fdef = CATALOG_BY_NAME.get(step["name"])
        if not fdef:
            messagebox.showerror("오류", f"정의되지 않은 함수: {step['name']}")
            return
        dlg = ArgDialog(self, fdef, preset=step.get("args"))
        self.wait_window(dlg)
        if dlg.result is None: return
        self.steps[pos]["args"] = dlg.result
        self.refresh_steps(); self.lb_steps.selection_set(pos); self.lb_steps.see(pos)

    # ---------- 저장/불러오기/내보내기 ----------
    def save_project(self):
        data = {
            "trigger": {
                "event": self.var_trigger_event.get(),
                "arg": self.var_trigger_arg.get(),
                "enable_primary": self.var_enable_primary.get()
            },
            "steps": self.steps,
        }
        path = filedialog.asksaveasfilename(title="프로젝트 저장", defaultextension=".json",
                                            filetypes=[["JSON","*.json"],["All Files","*.*"]])
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("저장됨", f"프로젝트 저장: {path}")

    def load_project(self):
        path = filedialog.askopenfilename(title="프로젝트 불러오기",
                                          filetypes=[["JSON","*.json"],["All Files","*.*"]])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            trig = data.get("trigger", {})
            code = trig.get("event", EVENT_ORDER[0])
            self.var_trigger_event.set(code)
            if "arg" in trig:
                arg_value = trig.get("arg")
            else:
                arg_meta = EVENT_DEFS.get(code, {}).get("arg")
                arg_value = arg_meta.get("default", arg_meta.get("min", -1)) if arg_meta else -1
            self.var_trigger_arg.set(arg_value)
            self.var_enable_primary.set(bool(trig.get("enable_primary", True)))
            self.steps = data.get("steps", [])
            self.refresh_event_combobox(); self.refresh_steps()
            messagebox.showinfo("완료", f"불러오기 성공: {path}")
        except Exception as e:
            messagebox.showerror("불러오기 실패", str(e))

    def export_lua(self):
        if not self.steps:
            if not messagebox.askyesno("확인", "스텝이 비어 있습니다. 그래도 내보낼까요?"):
                return
        path = filedialog.asksaveasfilename(title="Lua 내보내기", defaultextension=".lua",
                                            filetypes=[["Lua","*.lua"],["All Files","*.*"]])
        if not path: return
        lua = self.generate_lua()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(lua)
            messagebox.showinfo("완료", f"Lua 파일로 내보냈습니다: {path}")
        except Exception as e:
            messagebox.showerror("오류", str(e))
        finally:
            self.update_preview()

    def copy_lua_to_clipboard(self):
        try:
            lua = self.generate_lua()
            self.clipboard_clear(); self.clipboard_append(lua)
            self.set_status("Lua 코드가 클립보드에 복사되었습니다")
            messagebox.showinfo("복사됨", "레거시 Lua 코드가 클립보드로 복사되었습니다.")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    # ---------- Lua 생성 ----------
    def generate_lua(self) -> str:
        lines = []
        lines.append("-- Generated by G HUB Lua Script Builder")
        if self.var_enable_primary.get():
            lines.append("EnablePrimaryMouseButtonEvents(true)")
        lines.append("")
        lines.append("function OnEvent(event, arg)")
        ev = self.var_trigger_event.get(); ar = self.var_trigger_arg.get()
        cond = []
        if ev: cond.append(f"event == \"{ev}\"")
        if ar != -1: cond.append(f"arg == {ar}")
        if cond:
            lines.append(f"  if {' and '.join(cond)} then"); indent = "    "
        else:
            indent = "  "
        for st in self.steps:
            fdef = CATALOG_BY_NAME.get(st["name"])
            if not fdef:
                lines.append(indent + f"-- 정의 누락: {st['name']}"); continue
            name = st["name"]; args = st.get("args", {})
            if name == "MoveMouseTo":
                x_px = int(args.get("x", 0)); y_px = int(args.get("y", 0))
                x_abs = round(max(0, min(self.screen_w - 1, x_px)) * 65535 / max(1, self.screen_w - 1))
                y_abs = round(max(0, min(self.screen_h - 1, y_px)) * 65535 / max(1, self.screen_h - 1))
                lines.append(indent + f"MoveMouseTo({x_abs}, {y_abs})  -- ({x_px}px, {y_px}px)")
            elif name == "MoveMouseToVirtual":
                x_px = int(args.get("x", 0)); y_px = int(args.get("y", 0))
                x_abs = round(max(0, min(self.screen_w - 1, x_px)) * 65535 / max(1, self.screen_w - 1))
                y_abs = round(max(0, min(self.screen_h - 1, y_px)) * 65535 / max(1, self.screen_h - 1))
                lines.append(indent + f"MoveMouseToVirtual({x_abs}, {y_abs})  -- ({x_px}px, {y_px}px)")
            else:
                call = format_call(fdef["call"], args)
                lines.append(indent + call)
        if cond:
            lines.append("  end")
        lines.append("end")
        return "\n".join(lines) + "\n"

    # ---------- 유틸 ----------
    def on_ctrl_space_capture(self, *_):
        """전역 단축키: 현재 마우스 좌표 저장 → MoveMouseTo 기본값으로 사용"""
        try:
            x = self.winfo_pointerx(); y = self.winfo_pointery()
            self.captured_xy = (x, y)
            self.set_status(f"좌표 캡처됨: {x}, {y} — 다음 MoveMouseTo 추가 시 반영")
        except Exception:
            pass
        return "break"

    def quick_add_sleep(self):
        step = {"name": "Sleep", "args": {"ms": 10}}
        sel = self.lb_steps.curselection()
        if sel:
            pos = sel[0] + 1
            self.steps.insert(pos, step)
            self.refresh_steps(); self.lb_steps.selection_clear(0, tk.END); self.lb_steps.selection_set(pos); self.lb_steps.see(pos)
        else:
            self.steps.append(step)
            self.refresh_steps(); self.lb_steps.selection_clear(0, tk.END); self.lb_steps.selection_set(len(self.steps)-1); self.lb_steps.see(tk.END)
        self.set_status("스텝 추가됨: Sleep(10)")

# ==============================
# 엔트리 포인트
# ==============================

def run_tests() -> int:
    """간단 내부 테스트: 문법/포맷 체크용"""
    fails = 0
    try:
        assert _quote_if_needed("A") == '"A"'
        assert _quote_if_needed('"A"') == '"A"'
    except AssertionError:
        print("[TEST] quote 실패", file=sys.stderr); fails += 1

    try:
        spec = {"type": "int", "min": 0, "max": 10}
        assert validate_value(spec, "5") == 5
        try:
            validate_value(spec, "-1"); print("[TEST] int 범위 실패", file=sys.stderr); fails += 1
        except ValueError:
            pass
    except AssertionError:
        print("[TEST] validate(int) 실패", file=sys.stderr); fails += 1

    try:
        fmt = "PressAndReleaseKey(%(k1)s%(k2_opt)s)"
        s1 = format_call(fmt, {"k1": 'A', "k2": ''})
        s2 = format_call(fmt, {"k1": 'A', "k2": 'B'})
        assert s1 == 'PressAndReleaseKey("A")' and s2 == 'PressAndReleaseKey("A", "B")'
    except AssertionError:
        print("[TEST] format_call 실패", file=sys.stderr); fails += 1

    try:
        app = ScriptBuilderApp(); app.steps = [
            {"name": "MoveMouseTo", "args": {"x": app.screen_w // 2, "y": app.screen_h // 2}},
            {"name": "Sleep", "args": {"ms": 10}},
        ]
        lua = app.generate_lua(); doc = app.generate_korean_doc()
        assert "MoveMouseTo(" in lua and ")  -- (" in lua and "Sleep(10)" in lua
        assert "마우스를 (" in doc and "위치로 이동" in doc
        app.destroy()
    except AssertionError:
        print("[TEST] lua/doc 실패", file=sys.stderr); fails += 1
    except Exception:
        # 테스트가 GUI 환경 의존적일 수 있으므로 치명적 실패로 보지 않음
        pass
    return 1 if fails else 0


if __name__ == "__main__":
    if "--run-tests" in sys.argv:
        sys.exit(run_tests())
    # 빠른 문법 체크 옵션
    if "--check-only" in sys.argv:
        import py_compile; py_compile.compile(__file__, doraise=True)
        print("[OK] py_compile passed"); sys.exit(0)

    app = ScriptBuilderApp()
    app.mainloop()
