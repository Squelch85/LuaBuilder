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
import copy
import json
import sys
import tkinter as tk
from typing import Callable
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

    {"name": "__CALL_USER_FUNCTION__", "cat": "Custom", "icon": "🧩",
     "call": "%(func)s(%(arg_expr)s)",
     "args": [
         {"name": "func", "label": "로컬 함수", "type": "choice", "choices": "__USER_FUNCS__", "default": ""},
         {"name": "arg_expr", "label": "인수 표현식", "type": "raw", "default": ""},
     ],
     "desc": "사용자 정의 함수 호출"},
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
    if t == "raw":
        return str(value_str)
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
    def __init__(self, app, func_def, preset=None, schedule=None, settings=None,
                 allow_schedule: bool = False, allow_settings: bool = False):
        super().__init__(app)
        self.title(f"인수 입력 — {func_def['name']}")
        self.resizable(False, False)
        self.func_def = func_def
        self.app = app
        self.result = None
        self._key_capture_target = None  # "k1"/"k2"/"key"
        self.allow_schedule = allow_schedule
        self.allow_settings = allow_settings
        self.schedule_vars: dict[str, tk.Variable] = {}
        self.settings_text: tk.Text | None = None

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")
        frm.columnconfigure(1, weight=1)

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

        schedule_row = len(func_def.get("args", [])) + 1
        if allow_schedule:
            sched = schedule.copy() if schedule else self.app.get_default_schedule()
            sfrm = ttk.LabelFrame(frm, text="타이밍/스케줄")
            sfrm.grid(row=schedule_row, column=0, columnspan=2, sticky="ew", pady=(10, 0))

            self.schedule_vars = {
                "start_delay": tk.StringVar(value=str(sched.get("start_delay", 0))),
                "interval": tk.StringVar(value=str(sched.get("interval", 0))),
                "repeat": tk.StringVar(value=str(sched.get("repeat", 1))),
                "cooldown": tk.StringVar(value=str(sched.get("cooldown", 0))),
                "loop_var": tk.StringVar(value=str(sched.get("loop_var", "i"))),
            }

            ttk.Label(sfrm, text="시작 지연(ms)").grid(row=0, column=0, sticky="w", padx=4, pady=2)
            ttk.Spinbox(sfrm, from_=0, to=600000, increment=10,
                        textvariable=self.schedule_vars["start_delay"], width=10).grid(row=0, column=1, padx=4, pady=2)

            ttk.Label(sfrm, text="반복 간격(ms)").grid(row=1, column=0, sticky="w", padx=4, pady=2)
            ttk.Spinbox(sfrm, from_=0, to=600000, increment=10,
                        textvariable=self.schedule_vars["interval"], width=10).grid(row=1, column=1, padx=4, pady=2)

            ttk.Label(sfrm, text="반복 횟수").grid(row=2, column=0, sticky="w", padx=4, pady=2)
            ttk.Spinbox(sfrm, from_=1, to=9999, increment=1,
                        textvariable=self.schedule_vars["repeat"], width=10).grid(row=2, column=1, padx=4, pady=2)

            ttk.Label(sfrm, text="종료 후 대기(ms)").grid(row=3, column=0, sticky="w", padx=4, pady=2)
            ttk.Spinbox(sfrm, from_=0, to=600000, increment=10,
                        textvariable=self.schedule_vars["cooldown"], width=10).grid(row=3, column=1, padx=4, pady=2)

            ttk.Label(sfrm, text="루프 변수명").grid(row=4, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(sfrm, textvariable=self.schedule_vars["loop_var"], width=12).grid(row=4, column=1, padx=4, pady=2, sticky="w")

        settings_row = schedule_row + (1 if allow_schedule else 0)
        if allow_settings:
            setfrm = ttk.LabelFrame(frm, text="지역 설정(JSON)")
            setfrm.grid(row=settings_row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            self.settings_text = tk.Text(setfrm, width=46, height=5)
            self.settings_text.grid(row=0, column=0, sticky="ew")
            if settings:
                try:
                    self.settings_text.insert("1.0", json.dumps(settings, ensure_ascii=False, indent=2))
                except Exception:
                    self.settings_text.insert("1.0", str(settings))
            else:
                self.settings_text.insert("1.0", "{}")

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
            schedule_result = None
            if self.allow_schedule:
                try:
                    schedule_result = {
                        "start_delay": max(0, int(str(self.schedule_vars["start_delay"].get()).strip() or 0)),
                        "interval": max(0, int(str(self.schedule_vars["interval"].get()).strip() or 0)),
                        "repeat": max(1, int(str(self.schedule_vars["repeat"].get()).strip() or 1)),
                        "cooldown": max(0, int(str(self.schedule_vars["cooldown"].get()).strip() or 0)),
                        "loop_var": (str(self.schedule_vars["loop_var"].get()).strip() or "i"),
                    }
                except ValueError:
                    raise ValueError("스케줄 값은 정수여야 합니다.")

            settings_result = None
            if self.allow_settings and self.settings_text is not None:
                raw_text = self.settings_text.get("1.0", tk.END).strip()
                settings_result = {}
                if raw_text:
                    try:
                        settings_result = json.loads(raw_text)
                        if not isinstance(settings_result, dict):
                            raise ValueError("지역 설정은 JSON 객체 형태여야 합니다.")
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"지역 설정 JSON 구문 오류: {exc}")
            self.result = {
                "args": vals,
                "schedule": schedule_result,
                "settings": settings_result,
            }
            self.destroy()
        except Exception as e:
            messagebox.showerror("입력 오류", str(e), parent=self)

    def on_cancel(self):
        self.result = None
        self.destroy()


class BlockDialog(tk.Toplevel):
    BLOCK_TYPES = [
        ("repeat", "반복 루프"),
        ("while", "While 조건"),
        ("if", "조건 분기"),
    ]

    def __init__(self, app, block=None):
        super().__init__(app)
        self.app = app
        self.block = block or {}
        self.result = None

        self.title("블록 설정")
        self.resizable(False, False)

        meta = self.block.get("meta", {}) or {}
        schedule = app.normalize_schedule(self.block.get("schedule")) if block else app.get_default_schedule()
        settings = self.block.get("settings") or {}
        self.original_block_type = self.block.get("block_type")

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        label_map = {code: label for code, label in self.BLOCK_TYPES}
        self.type_map = {label: code for code, label in self.BLOCK_TYPES}
        initial_type = self.block.get("block_type", "repeat")
        initial_label = label_map.get(initial_type, label_map["repeat"])
        ttk.Label(frm, text="블록 종류:").grid(row=0, column=0, sticky="w", pady=4)
        self.var_type = tk.StringVar(value=initial_label)
        cb = ttk.Combobox(frm, textvariable=self.var_type, values=list(label_map.values()), state="readonly", width=24)
        cb.grid(row=0, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda *_: self.render_meta_fields())

        self.meta_frame = ttk.LabelFrame(frm, text="블록 속성")
        self.meta_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8,0))
        self.meta_vars: dict[str, tk.StringVar] = {}
        self.meta_data = meta
        self.render_meta_fields()

        self.schedule_vars = {
            "start_delay": tk.StringVar(value=str(schedule.get("start_delay", 0))),
            "interval": tk.StringVar(value=str(schedule.get("interval", 0))),
            "repeat": tk.StringVar(value=str(schedule.get("repeat", 1))),
            "cooldown": tk.StringVar(value=str(schedule.get("cooldown", 0))),
            "loop_var": tk.StringVar(value=str(schedule.get("loop_var", "i"))),
        }
        sfrm = ttk.LabelFrame(frm, text="타이밍/스케줄")
        sfrm.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10,0))
        ttk.Label(sfrm, text="시작 지연(ms)").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(sfrm, from_=0, to=600000, increment=10, textvariable=self.schedule_vars["start_delay"], width=10).grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(sfrm, text="반복 간격(ms)").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(sfrm, from_=0, to=600000, increment=10, textvariable=self.schedule_vars["interval"], width=10).grid(row=1, column=1, padx=4, pady=2)
        ttk.Label(sfrm, text="반복 횟수").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(sfrm, from_=1, to=9999, increment=1, textvariable=self.schedule_vars["repeat"], width=10).grid(row=2, column=1, padx=4, pady=2)
        ttk.Label(sfrm, text="종료 후 대기(ms)").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(sfrm, from_=0, to=600000, increment=10, textvariable=self.schedule_vars["cooldown"], width=10).grid(row=3, column=1, padx=4, pady=2)
        ttk.Label(sfrm, text="루프 변수명").grid(row=4, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(sfrm, textvariable=self.schedule_vars["loop_var"], width=12).grid(row=4, column=1, padx=4, pady=2, sticky="w")

        setfrm = ttk.LabelFrame(frm, text="지역 설정(JSON)")
        setfrm.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10,0))
        self.txt_settings = tk.Text(setfrm, width=46, height=5)
        self.txt_settings.grid(row=0, column=0, sticky="ew")
        if settings:
            try:
                self.txt_settings.insert("1.0", json.dumps(settings, ensure_ascii=False, indent=2))
            except Exception:
                self.txt_settings.insert("1.0", str(settings))
        else:
            self.txt_settings.insert("1.0", "{}")

        btnfrm = ttk.Frame(frm)
        btnfrm.grid(row=4, column=0, columnspan=2, pady=(12,0))
        ttk.Button(btnfrm, text="확인", command=self.on_ok).grid(row=0, column=0, padx=4)
        ttk.Button(btnfrm, text="취소", command=self.on_cancel).grid(row=0, column=1, padx=4)

        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.on_cancel())

        self.transient(app)
        self.grab_set()
        self.update_idletasks()
        self.center_to_parent()
        self.focus_set()

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

    def current_block_type(self) -> str:
        label = self.var_type.get()
        return self.type_map.get(label, "repeat")

    def render_meta_fields(self):
        for child in self.meta_frame.winfo_children():
            child.destroy()
        btype = self.current_block_type()
        meta = self.meta_data if self.original_block_type == btype else {}
        if btype == "repeat":
            self.meta_vars["count"] = tk.StringVar(value=str(meta.get("count", 1)))
            self.meta_vars["var_name"] = tk.StringVar(value=meta.get("var_name") or meta.get("loop_var") or self.app.get_default_schedule().get("loop_var", "i"))
            self.meta_vars["label"] = tk.StringVar(value=meta.get("label", ""))
            ttk.Label(self.meta_frame, text="반복 횟수").grid(row=0, column=0, sticky="w", padx=4, pady=2)
            ttk.Spinbox(self.meta_frame, from_=1, to=9999, increment=1, textvariable=self.meta_vars["count"], width=10).grid(row=0, column=1, sticky="w", padx=4, pady=2)
            ttk.Label(self.meta_frame, text="루프 변수명").grid(row=1, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(self.meta_frame, textvariable=self.meta_vars["var_name"], width=16).grid(row=1, column=1, sticky="w", padx=4, pady=2)
            ttk.Label(self.meta_frame, text="라벨/설명").grid(row=2, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(self.meta_frame, textvariable=self.meta_vars["label"], width=32).grid(row=2, column=1, sticky="w", padx=4, pady=2)
        elif btype in ("while", "if"):
            self.meta_vars["condition"] = tk.StringVar(value=meta.get("condition", "true"))
            self.meta_vars["label"] = tk.StringVar(value=meta.get("label", ""))
            ttk.Label(self.meta_frame, text="조건 표현식").grid(row=0, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(self.meta_frame, textvariable=self.meta_vars["condition"], width=34).grid(row=0, column=1, sticky="w", padx=4, pady=2)
            ttk.Label(self.meta_frame, text="라벨/설명").grid(row=1, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(self.meta_frame, textvariable=self.meta_vars["label"], width=32).grid(row=1, column=1, sticky="w", padx=4, pady=2)
        else:
            ttk.Label(self.meta_frame, text="이 블록 유형은 추가 설정이 없습니다.").grid(row=0, column=0, sticky="w", padx=4, pady=2)

    def on_ok(self):
        try:
            block_type = self.current_block_type()
            meta: dict[str, object] = {}
            if block_type == "repeat":
                count = int(str(self.meta_vars["count"].get()).strip() or 1)
                if count < 1:
                    raise ValueError("반복 횟수는 1 이상이어야 합니다.")
                meta["count"] = count
                var_name = str(self.meta_vars["var_name"].get()).strip() or self.schedule_vars["loop_var"].get() or "i"
                meta["var_name"] = var_name
                label = str(self.meta_vars["label"].get()).strip()
                if label:
                    meta["label"] = label
            elif block_type in ("while", "if"):
                condition = str(self.meta_vars["condition"].get()).strip() or "true"
                meta["condition"] = condition
                label = str(self.meta_vars["label"].get()).strip()
                if label:
                    meta["label"] = label

            schedule_result = {
                "start_delay": max(0, int(str(self.schedule_vars["start_delay"].get()).strip() or 0)),
                "interval": max(0, int(str(self.schedule_vars["interval"].get()).strip() or 0)),
                "repeat": max(1, int(str(self.schedule_vars["repeat"].get()).strip() or 1)),
                "cooldown": max(0, int(str(self.schedule_vars["cooldown"].get()).strip() or 0)),
                "loop_var": str(self.schedule_vars["loop_var"].get()).strip() or "i",
            }

            settings_text = self.txt_settings.get("1.0", tk.END).strip()
            settings_result = {}
            if settings_text:
                try:
                    settings_result = json.loads(settings_text)
                    if not isinstance(settings_result, dict):
                        raise ValueError("지역 설정은 JSON 객체 형태여야 합니다.")
                except json.JSONDecodeError as exc:
                    raise ValueError(f"지역 설정 JSON 구문 오류: {exc}") from exc

            self.result = {
                "block_type": block_type,
                "meta": meta,
                "schedule": schedule_result,
                "settings": settings_result,
            }
            self.destroy()
        except Exception as e:
            messagebox.showerror("입력 오류", str(e), parent=self)

    def on_cancel(self):
        self.result = None
        self.destroy()


class FunctionDialog(tk.Toplevel):
    def __init__(self, app, func=None):
        super().__init__(app)
        self.result = None
        self.title("로컬 함수 설정")
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        self.var_name = tk.StringVar(value=(func or {}).get("name", ""))
        ttk.Label(frm, text="함수 이름:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.var_name, width=30).grid(row=0, column=1, sticky="w")

        params = ", ".join((func or {}).get("params", []))
        self.var_params = tk.StringVar(value=params)
        ttk.Label(frm, text="매개변수(콤마 구분):").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.var_params, width=34).grid(row=1, column=1, sticky="w")

        ttk.Label(frm, text="설명").grid(row=2, column=0, sticky="nw", pady=4)
        self.txt_desc = tk.Text(frm, width=40, height=4)
        self.txt_desc.grid(row=2, column=1, sticky="ew")
        desc = (func or {}).get("description", "")
        if desc:
            self.txt_desc.insert("1.0", desc)

        ttk.Label(frm, text="설정(JSON)").grid(row=3, column=0, sticky="nw", pady=4)
        self.txt_settings = tk.Text(frm, width=40, height=5)
        self.txt_settings.grid(row=3, column=1, sticky="ew")
        settings = (func or {}).get("settings", {})
        if settings:
            try:
                self.txt_settings.insert("1.0", json.dumps(settings, ensure_ascii=False, indent=2))
            except Exception:
                self.txt_settings.insert("1.0", str(settings))
        else:
            self.txt_settings.insert("1.0", "{}")

        btnfrm = ttk.Frame(frm)
        btnfrm.grid(row=4, column=0, columnspan=2, pady=(12,0))
        ttk.Button(btnfrm, text="확인", command=self.on_ok).grid(row=0, column=0, padx=4)
        ttk.Button(btnfrm, text="취소", command=self.on_cancel).grid(row=0, column=1, padx=4)

        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.on_cancel())

        self.transient(app)
        self.grab_set()
        self.update_idletasks()
        self.center_to_parent()
        self.focus_set()

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

    def on_ok(self):
        try:
            name = self.var_name.get().strip()
            if not name:
                raise ValueError("함수 이름을 입력하세요.")
            if not (name[0].isalpha() or name[0] == "_") or not all(c.isalnum() or c == "_" for c in name):
                raise ValueError("함수 이름은 영문/숫자/밑줄만 사용할 수 있으며 숫자로 시작할 수 없습니다.")
            params = [p.strip() for p in self.var_params.get().split(",") if p.strip()]
            desc = self.txt_desc.get("1.0", tk.END).strip()
            settings_text = self.txt_settings.get("1.0", tk.END).strip()
            settings = {}
            if settings_text:
                try:
                    settings = json.loads(settings_text)
                    if not isinstance(settings, dict):
                        raise ValueError("설정은 JSON 객체 형태여야 합니다.")
                except json.JSONDecodeError as exc:
                    raise ValueError(f"설정 JSON 구문 오류: {exc}") from exc
            self.result = {
                "name": name,
                "params": params,
                "description": desc,
                "settings": settings,
            }
            self.destroy()
        except Exception as e:
            messagebox.showerror("입력 오류", str(e), parent=self)

    def on_cancel(self):
        self.result = None
        self.destroy()


class GlobalSettingsDialog(tk.Toplevel):
    def __init__(self, app, settings):
        super().__init__(app)
        self.app = app
        self.result = None
        self.title("전역 설정")
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        base_schedule = app.normalize_schedule((settings or {}).get("default_schedule"))
        self.schedule_vars = {
            "start_delay": tk.StringVar(value=str(base_schedule.get("start_delay", 0))),
            "interval": tk.StringVar(value=str(base_schedule.get("interval", 0))),
            "repeat": tk.StringVar(value=str(base_schedule.get("repeat", 1))),
            "cooldown": tk.StringVar(value=str(base_schedule.get("cooldown", 0))),
            "loop_var": tk.StringVar(value=str(base_schedule.get("loop_var", "i"))),
        }
        sfrm = ttk.LabelFrame(frm, text="신규 스텝 기본 스케줄")
        sfrm.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(sfrm, text="시작 지연(ms)").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(sfrm, from_=0, to=600000, increment=10, textvariable=self.schedule_vars["start_delay"], width=10).grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(sfrm, text="반복 간격(ms)").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(sfrm, from_=0, to=600000, increment=10, textvariable=self.schedule_vars["interval"], width=10).grid(row=1, column=1, padx=4, pady=2)
        ttk.Label(sfrm, text="반복 횟수").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(sfrm, from_=1, to=9999, increment=1, textvariable=self.schedule_vars["repeat"], width=10).grid(row=2, column=1, padx=4, pady=2)
        ttk.Label(sfrm, text="종료 후 대기(ms)").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(sfrm, from_=0, to=600000, increment=10, textvariable=self.schedule_vars["cooldown"], width=10).grid(row=3, column=1, padx=4, pady=2)
        ttk.Label(sfrm, text="루프 변수명").grid(row=4, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(sfrm, textvariable=self.schedule_vars["loop_var"], width=12).grid(row=4, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(frm, text="Prelude Lua 코드").grid(row=1, column=0, sticky="nw", pady=(10,2))
        self.txt_prelude = tk.Text(frm, width=48, height=4)
        self.txt_prelude.grid(row=1, column=1, sticky="ew", pady=(10,2))
        prelude = (settings or {}).get("prelude", "")
        if prelude:
            self.txt_prelude.insert("1.0", prelude)

        ttk.Label(frm, text="전역 노트").grid(row=2, column=0, sticky="nw", pady=2)
        self.txt_notes = tk.Text(frm, width=48, height=4)
        self.txt_notes.grid(row=2, column=1, sticky="ew")
        notes = (settings or {}).get("notes", "")
        if notes:
            self.txt_notes.insert("1.0", notes)

        ttk.Label(frm, text="기타 설정(JSON)").grid(row=3, column=0, sticky="nw", pady=2)
        self.txt_custom = tk.Text(frm, width=48, height=4)
        self.txt_custom.grid(row=3, column=1, sticky="ew")
        custom = (settings or {}).get("custom", {})
        if custom:
            try:
                self.txt_custom.insert("1.0", json.dumps(custom, ensure_ascii=False, indent=2))
            except Exception:
                self.txt_custom.insert("1.0", str(custom))
        else:
            self.txt_custom.insert("1.0", "{}")

        btnfrm = ttk.Frame(frm)
        btnfrm.grid(row=4, column=0, columnspan=2, pady=(12,0))
        ttk.Button(btnfrm, text="확인", command=self.on_ok).grid(row=0, column=0, padx=4)
        ttk.Button(btnfrm, text="취소", command=self.on_cancel).grid(row=0, column=1, padx=4)

        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.on_cancel())

        self.transient(app)
        self.grab_set()
        self.update_idletasks()
        self.center_to_parent()
        self.focus_set()

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

    def on_ok(self):
        try:
            schedule = {
                "start_delay": max(0, int(str(self.schedule_vars["start_delay"].get()).strip() or 0)),
                "interval": max(0, int(str(self.schedule_vars["interval"].get()).strip() or 0)),
                "repeat": max(1, int(str(self.schedule_vars["repeat"].get()).strip() or 1)),
                "cooldown": max(0, int(str(self.schedule_vars["cooldown"].get()).strip() or 0)),
                "loop_var": str(self.schedule_vars["loop_var"].get()).strip() or "i",
            }
            prelude = self.txt_prelude.get("1.0", tk.END).rstrip()
            notes = self.txt_notes.get("1.0", tk.END).rstrip()
            custom_text = self.txt_custom.get("1.0", tk.END).strip()
            custom = {}
            if custom_text:
                try:
                    custom = json.loads(custom_text)
                    if not isinstance(custom, dict):
                        raise ValueError("기타 설정은 JSON 객체 형태여야 합니다.")
                except json.JSONDecodeError as exc:
                    raise ValueError(f"기타 설정 JSON 구문 오류: {exc}") from exc
            self.result = {
                "default_schedule": schedule,
                "prelude": prelude,
                "notes": notes,
                "custom": custom,
            }
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

        self.global_settings: dict = {
            "default_schedule": {
                "start_delay": 0,
                "interval": 0,
                "repeat": 1,
                "cooldown": 0,
                "loop_var": "i",
            },
            "prelude": "",
            "notes": "",
            "custom": {},
        }
        self.root_block = self._make_root_block()
        self.functions: list[dict] = []
        self.flat_steps: list[dict] = []
        self.var_scope = tk.StringVar()

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
        self.update_scope_options()
        self.refresh_steps()
        self.update_preview()

    # ---------- 데이터 헬퍼 ----------
    def _make_root_block(self) -> dict:
        return self.make_block_step("root")

    def sanitize_schedule_dict(self, schedule: dict | None) -> dict:
        schedule = schedule or {}
        return {
            "start_delay": max(0, int(schedule.get("start_delay", 0) or 0)),
            "interval": max(0, int(schedule.get("interval", 0) or 0)),
            "repeat": max(1, int(schedule.get("repeat", 1) or 1)),
            "cooldown": max(0, int(schedule.get("cooldown", 0) or 0)),
            "loop_var": str(schedule.get("loop_var", "i") or "i"),
        }

    def get_default_schedule(self) -> dict:
        base = self.global_settings.get("default_schedule", {}) if hasattr(self, "global_settings") else {}
        return self.sanitize_schedule_dict(base)

    def normalize_schedule(self, schedule: dict | None) -> dict:
        base = self.get_default_schedule()
        if not schedule:
            return dict(base)
        sanitized = self.sanitize_schedule_dict(schedule)
        normalized = dict(base)
        normalized.update(sanitized)
        return normalized

    def get_user_function_names(self) -> list[str]:
        return [fn.get("name") for fn in self.functions if fn.get("name")]

    def resolve_dynamic_choices(self, func_def: dict):
        for spec in func_def.get("args", []):
            choices = spec.get("choices")
            if isinstance(choices, str) and choices == "__USER_FUNCS__":
                names = [name for name in self.get_user_function_names() if name]
                spec["choices"] = [""] + names if names else [""]
                # 로컬 함수가 존재하면 기본값을 첫 항목으로 자동 지정해 빈 호출 생성 방지
                if names and not spec.get("default"):
                    spec["default"] = names[0]

    def make_action_step(self, name: str, args: dict | None = None,
                         schedule: dict | None = None, settings: dict | None = None) -> dict:
        return {
            "type": "action",
            "name": name,
            "args": args or {},
            "schedule": self.normalize_schedule(schedule),
            "settings": settings or {},
        }

    def make_block_step(self, block_type: str, meta: dict | None = None,
                        schedule: dict | None = None, settings: dict | None = None,
                        children: list | None = None) -> dict:
        return {
            "type": "block",
            "block_type": block_type,
            "meta": meta or {},
            "children": children or [],
            "schedule": self.normalize_schedule(schedule),
            "settings": settings or {},
        }

    def migrate_step(self, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        st_type = data.get("type")
        if st_type == "block":
            children = [self.migrate_step(ch) for ch in data.get("children", [])]
            return self.make_block_step(
                data.get("block_type", "block"),
                meta=data.get("meta", {}),
                schedule=data.get("schedule"),
                settings=data.get("settings"),
                children=children,
            )
        if st_type == "action":
            return self.make_action_step(
                data.get("name", ""),
                args=data.get("args", {}),
                schedule=data.get("schedule"),
                settings=data.get("settings"),
            )
        return self.make_action_step(data.get("name", ""), args=data.get("args", {}))

    def update_scope_options(self):
        options = [("main", None, "메인 스크립트")]
        for idx, fn in enumerate(self.functions):
            label = f"함수: {fn.get('name', f'Function{idx+1}') }"
            options.append(("function", idx, label))
        self.scope_options = options
        labels = [opt[2] for opt in options]
        current = self.var_scope.get()
        if not labels:
            self.var_scope.set("")
        elif current not in labels:
            self.var_scope.set(labels[0])
        if hasattr(self, "cb_scope"):
            self.cb_scope["values"] = labels
            if labels:
                self.cb_scope.set(self.var_scope.get())
            else:
                self.cb_scope.set("")

    def on_scope_changed(self, *_):
        if hasattr(self, "cb_scope") and self.cb_scope.get() != self.var_scope.get():
            self.var_scope.set(self.cb_scope.get())
        self.refresh_steps()
        self.update_preview()

    def get_active_root(self) -> dict:
        label = self.var_scope.get()
        for kind, idx, lbl in getattr(self, "scope_options", []):
            if lbl == label:
                if kind == "function" and idx is not None and 0 <= idx < len(self.functions):
                    return self.functions[idx].setdefault("body", self._make_root_block())
                break
        return self.root_block

    def get_active_children(self) -> list:
        return self.get_active_root().setdefault("children", [])

    def rebuild_flat_steps(self):
        self.flat_steps = []

        def visit(children: list, depth: int, path_prefix: list[int]):
            for idx, step in enumerate(children):
                path = path_prefix + [idx]
                self.flat_steps.append({
                    "path": path,
                    "step": step,
                    "depth": depth,
                })
                if step.get("type") == "block":
                    visit(step.get("children", []), depth + 1, path)

        visit(self.get_active_children(), 0, [])

    def summarize_schedule(self, schedule: dict | None) -> str:
        sch = self.normalize_schedule(schedule)
        parts = []
        if sch.get("start_delay"):
            parts.append(f"지연 {sch['start_delay']}ms")
        if sch.get("repeat", 1) > 1:
            parts.append(f"{sch['repeat']}회 반복")
        if sch.get("interval"):
            parts.append(f"간격 {sch['interval']}ms")
        if sch.get("cooldown"):
            parts.append(f"종료 후 {sch['cooldown']}ms")
        return ", ".join(parts)

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
        ttk.Button(center, text="블록 추가…", command=self.add_block_step, width=14).pack(pady=4)
        ttk.Button(center, text="← 삭제", command=self.remove_selected_steps, width=14).pack(pady=4)
        ttk.Separator(center, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Button(center, text="위로 ↑", command=lambda: self.move_selected_steps(-1), width=14).pack(pady=4)
        ttk.Button(center, text="아래로 ↓", command=lambda: self.move_selected_steps(1), width=14).pack(pady=4)
        ttk.Button(center, text="복제", command=self.duplicate_selected_steps, width=14).pack(pady=12)
        ttk.Button(center, text="들여쓰기", command=self.indent_selected_step, width=14).pack(pady=4)
        ttk.Button(center, text="내어쓰기", command=self.outdent_selected_step, width=14).pack(pady=4)

        # 우: 스텝 리스트 + 미리보기
        right = ttk.Frame(mid); mid.add(right, weight=2)
        scope_frm = ttk.Frame(right)
        scope_frm.pack(fill=tk.X, pady=(0,4))
        ttk.Label(scope_frm, text="편집 범위:").pack(side=tk.LEFT)
        self.cb_scope = ttk.Combobox(scope_frm, textvariable=self.var_scope, state="readonly", width=28)
        self.cb_scope.pack(side=tk.LEFT, padx=(4,4))
        self.cb_scope.bind("<<ComboboxSelected>>", self.on_scope_changed)
        ttk.Button(scope_frm, text="함수 추가", command=self.add_local_function).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(scope_frm, text="속성", command=self.configure_local_function).pack(side=tk.LEFT, padx=4)
        ttk.Button(scope_frm, text="삭제", command=self.remove_local_function).pack(side=tk.LEFT)

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
        ttk.Button(bottom, text="전역 설정…", command=self.open_global_settings).pack(side=tk.LEFT)
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
        lines.append(f"- 좌클릭 이벤트 전달 설정: EnablePrimaryMouseButtonEvents({'true' if self.var_enable_primary.get() else 'false'})")
        lines.append("")

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

        lines.append("메인 스크립트:")
        main_children = self.root_block.get("children", [])
        if not main_children:
            lines.append("  (스텝이 없습니다)")
        else:
            self._append_doc_steps(main_children, lines, depth=1)

        if self.functions:
            lines.append("")
            lines.append("로컬 함수:")
            for fn in self.functions:
                name = fn.get("name", "")
                params = ", ".join(fn.get("params", []))
                lines.append(f"  - {name}({params})")
                desc = fn.get("description", "")
                if desc:
                    for line in desc.splitlines():
                        lines.append(f"      · {line}")
                body = fn.get("body") or self._make_root_block()
                self._append_doc_steps(body.get("children", []), lines, depth=2)

        return "\n".join(lines) + "\n"

    def _append_doc_steps(self, steps: list, lines: list[str], depth: int):
        prefix = "  " * depth + "- "
        for step in steps:
            desc = self.localized_step_desc(step)
            schedule = self.summarize_schedule(step.get("schedule"))
            if schedule:
                desc += f" (스케줄: {schedule})"
            lines.append(prefix + desc)
            settings = step.get("settings") or {}
            note = settings.get("note") or settings.get("notes")
            if isinstance(note, str) and note.strip():
                for line in note.strip().splitlines():
                    lines.append("  " * (depth + 1) + f"· {line}")
            if step.get("type") == "block":
                self._append_doc_steps(step.get("children", []), lines, depth + 1)

    def localized_step_desc(self, step: dict) -> str:
        if step.get("type") == "block":
            block_type = step.get("block_type")
            meta = step.get("meta", {}) or {}
            label = meta.get("label") or meta.get("description") or ""
            if block_type == "repeat":
                count = int(meta.get("count", 1) or 1)
                loop_var = meta.get("var_name") or meta.get("loop_var") or self.normalize_schedule(step.get("schedule")).get("loop_var", "i")
                desc = f"반복 루프 {count}회 (변수 {loop_var})"
            elif block_type == "while":
                cond = meta.get("condition", "true") or "true"
                desc = f"While 루프 조건: {cond}"
            elif block_type == "if":
                cond = meta.get("condition", "true") or "true"
                desc = f"조건 분기: {cond}"
            elif block_type == "root":
                desc = "루트 블록"
            else:
                desc = f"블록({block_type})"
            if label:
                desc += f" — {label}"
            return desc

        name = step.get("name")
        a = step.get("args", {}) or {}
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
            if name == "__CALL_USER_FUNCTION__":
                target = a.get("func", "")
                expr = str(a.get("arg_expr", "")).strip()
                if expr:
                    return f"사용자 함수 호출: {target}({expr})"
                return f"사용자 함수 호출: {target}()"
        except Exception:
            pass
        return f"{name} (인수: {a})"

    # ---------- 스텝 조작 ----------
    def refresh_steps(self):
        self.rebuild_flat_steps()
        self.lb_steps.delete(0, tk.END)
        for info in self.flat_steps:
            indent = "    " * info["depth"]
            label = self.render_step_label(info["step"])
            self.lb_steps.insert(tk.END, indent + label)
        if self.flat_steps:
            self.lb_steps.see(len(self.flat_steps) - 1)
        self.update_preview()

    def render_step_label(self, step: dict) -> str:
        desc = self.localized_step_desc(step)
        parts = [desc]
        if step.get("type") == "block":
            parts.append(f"[{len(step.get('children', []))} 스텝]")
        schedule_info = self.summarize_schedule(step.get("schedule"))
        if schedule_info:
            parts.append(f"(스케줄: {schedule_info})")
        return " ".join(part for part in parts if part)

    def build_default_args(self, fdef: dict) -> dict:
        args = {}
        for spec in fdef.get("args", []):
            name = spec["name"]
            default = spec.get("default")
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
                args[name] = int(default if default is not None else 0)
            elif t == "bool":
                args[name] = bool(default)
            elif t == "choice":
                choices = spec.get("choices") or []
                if not choices:
                    args[name] = default if default is not None else ""
                else:
                    args[name] = default if default in choices else choices[0]
            elif t == "raw":
                args[name] = default or ""
            else:
                args[name] = default
        return args

    def get_selected_catalog_func(self):
        sel = self.tree.selection()
        if not sel:
            return None
        item = sel[0]
        vals = self.tree.set(item)
        if not vals:
            return None
        fname = vals.get("name")
        fdef = CATALOG_BY_NAME.get(fname)
        return copy.deepcopy(fdef) if fdef else None

    def get_selected_indices(self) -> list[int]:
        return [idx for idx in self.lb_steps.curselection() if idx < len(self.flat_steps)]

    def get_selected_paths(self) -> list[list[int]]:
        indices = self.get_selected_indices()
        return [self.flat_steps[idx]["path"] for idx in indices]

    def get_selected_path(self) -> list[int] | None:
        sel = self.get_selected_indices()
        if not sel:
            return None
        idx = sel[-1]
        return self.flat_steps[idx]["path"]

    def select_path(self, path: list[int] | None):
        if not path:
            self.lb_steps.selection_clear(0, tk.END)
            return
        self.select_paths([path])

    def select_indices(self, indices: list[int]):
        self.lb_steps.selection_clear(0, tk.END)
        if not indices:
            return
        first_visible = None
        for idx in indices:
            if 0 <= idx < len(self.flat_steps):
                if first_visible is None:
                    first_visible = idx
                self.lb_steps.selection_set(idx)
        if first_visible is not None:
            self.lb_steps.see(first_visible)

    def select_paths(self, paths: list[list[int]]):
        targets = {tuple(path) for path in paths}
        indices = [idx for idx, info in enumerate(self.flat_steps) if tuple(info["path"]) in targets]
        self.select_indices(indices)

    def get_step_by_path(self, path: list[int]) -> dict | None:
        node = self.get_active_root()
        for idx in path:
            children = node.setdefault("children", [])
            if not (0 <= idx < len(children)):
                return None
            node = children[idx]
        return node

    def get_parent_children(self, path: list[int]) -> list:
        if not path:
            return self.get_active_children()
        node = self.get_active_root()
        for idx in path[:-1]:
            children = node.setdefault("children", [])
            if not (0 <= idx < len(children)):
                return []
            node = children[idx]
        return node.setdefault("children", [])

    def insert_step_after(self, path: list[int] | None, step: dict) -> list[int]:
        if path is None:
            children = self.get_active_children()
            children.append(step)
            return [len(children) - 1]
        parent_children = self.get_parent_children(path)
        insert_index = min(len(parent_children), path[-1] + 1)
        parent_children.insert(insert_index, step)
        return path[:-1] + [insert_index]

    def add_selected_func(self):
        fdef = self.get_selected_catalog_func()
        if not fdef:
            messagebox.showinfo("안내", "함수를 선택하세요.")
            return
        self.resolve_dynamic_choices(fdef)
        if fdef["name"] == "__CALL_USER_FUNCTION__" and not self.get_user_function_names():
            messagebox.showwarning("로컬 함수 없음", "먼저 '로컬 함수' 탭에서 함수를 추가하세요.")
            return
        args = self.build_default_args(fdef)
        step = self.make_action_step(fdef["name"], args=args)
        new_path = self.insert_step_after(self.get_selected_path(), step)
        self.refresh_steps()
        self.select_path(new_path)
        self.set_status(f"스텝 추가됨: {step['name']}")

    def add_selected_func_with_dialog(self):
        fdef = self.get_selected_catalog_func()
        if not fdef:
            messagebox.showinfo("안내", "함수를 선택하세요.")
            return
        self.resolve_dynamic_choices(fdef)
        if fdef["name"] == "__CALL_USER_FUNCTION__" and not self.get_user_function_names():
            messagebox.showwarning("로컬 함수 없음", "먼저 '로컬 함수' 탭에서 함수를 추가하세요.")
            return
        preset_args = self.build_default_args(fdef)
        dlg = ArgDialog(self, fdef, preset=preset_args, schedule=self.get_default_schedule(),
                        settings={}, allow_schedule=True, allow_settings=True)
        self.wait_window(dlg)
        if not dlg.result:
            return
        result = dlg.result
        step = self.make_action_step(
            fdef["name"],
            args=result.get("args", {}),
            schedule=result.get("schedule"),
            settings=result.get("settings"),
        )
        new_path = self.insert_step_after(self.get_selected_path(), step)
        self.refresh_steps()
        self.select_path(new_path)
        self.set_status(f"스텝 추가됨: {step['name']} (상세 입력)")

    def add_block_step(self):
        dlg = BlockDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        result = dlg.result
        block = self.make_block_step(
            result["block_type"],
            meta=result.get("meta"),
            schedule=result.get("schedule"),
            settings=result.get("settings"),
            children=[],
        )
        new_path = self.insert_step_after(self.get_selected_path(), block)
        self.refresh_steps()
        self.select_path(new_path)
        self.set_status(f"블록 추가됨: {block['block_type']}")

    def remove_selected_steps(self):
        paths = self.get_selected_paths()
        if not paths:
            return
        indices = self.get_selected_indices()
        for path in sorted(paths, reverse=True):
            if not path:
                continue
            parent_children = self.get_parent_children(path)
            if not parent_children or not (0 <= path[-1] < len(parent_children)):
                continue
            parent_children.pop(path[-1])
        self.refresh_steps()
        if self.flat_steps and indices:
            new_idx = min(min(indices), len(self.flat_steps) - 1)
            self.select_indices([new_idx])
        else:
            self.lb_steps.selection_clear(0, tk.END)

    def duplicate_selected_steps(self):
        paths = self.get_selected_paths()
        if not paths:
            return
        new_paths: list[list[int]] = []
        for path in sorted(paths, reverse=True):
            step = self.get_step_by_path(path)
            if not step:
                continue
            cloned = copy.deepcopy(step)
            new_path = self.insert_step_after(path, cloned)
            new_paths.append(new_path)
        self.refresh_steps()
        if new_paths:
            self.select_paths(sorted(new_paths))

    def move_selected_steps(self, delta: int):
        infos = [self.flat_steps[idx] for idx in self.get_selected_indices()]
        if not infos:
            return
        parent_keys = {tuple(info["path"][:-1]) for info in infos}
        if len(parent_keys) != 1:
            messagebox.showinfo("안내", "같은 블록 내 스텝만 함께 이동할 수 있습니다.")
            return
        paths = sorted((info["path"] for info in infos), key=lambda p: p[-1])
        indices = [path[-1] for path in paths]
        if indices != list(range(indices[0], indices[0] + len(indices))):
            messagebox.showinfo("안내", "연속된 스텝만 함께 이동할 수 있습니다.")
            return
        parent_children = self.get_parent_children(paths[0])
        if not parent_children:
            return
        if delta < 0:
            if indices[0] == 0:
                return
        elif delta > 0:
            if indices[-1] >= len(parent_children) - 1:
                return
        else:
            return
        entries = [parent_children[idx] for idx in indices]
        for idx in sorted(indices, reverse=True):
            parent_children.pop(idx)
        insert_at = indices[0] + delta
        for offset, entry in enumerate(entries):
            parent_children.insert(insert_at + offset, entry)
        parent_path = list(paths[0][:-1])
        new_paths = [parent_path + [insert_at + offset] for offset in range(len(entries))]
        self.refresh_steps()
        self.select_paths(new_paths)

    def indent_selected_step(self):
        paths = self.get_selected_paths()
        if not paths:
            return
        parent_keys = {tuple(path[:-1]) for path in paths}
        if len(parent_keys) != 1:
            messagebox.showinfo("안내", "같은 블록 내 스텝만 선택해야 들여쓰기 할 수 있습니다.")
            return
        paths = sorted(paths, key=lambda p: p[-1])
        first = paths[0]
        if first[-1] == 0:
            return
        parent_children = self.get_parent_children(first)
        if not parent_children:
            return
        prev_step = parent_children[first[-1] - 1]
        if prev_step.get("type") != "block":
            messagebox.showinfo("안내", "이전 스텝이 블록이 아니어서 들여쓰기 할 수 없습니다.")
            return
        if [path[-1] for path in paths] != list(range(first[-1], first[-1] + len(paths))):
            messagebox.showinfo("안내", "연속된 스텝만 들여쓰기 할 수 있습니다.")
            return
        moved = []
        for path in sorted(paths, reverse=True):
            siblings = self.get_parent_children(path)
            moved.append(siblings.pop(path[-1]))
        moved.reverse()
        target_children = prev_step.setdefault("children", [])
        start_index = len(target_children)
        for step in moved:
            target_children.append(step)
        block_path = first[:-1] + [first[-1] - 1]
        new_paths = [block_path + [start_index + offset] for offset in range(len(moved))]
        self.refresh_steps()
        self.select_paths(new_paths)

    def outdent_selected_step(self):
        paths = self.get_selected_paths()
        if not paths:
            return
        parent_keys = {tuple(path[:-1]) for path in paths}
        if len(parent_keys) != 1:
            messagebox.showinfo("안내", "같은 블록 내 스텝만 내어쓰기 할 수 있습니다.")
            return
        paths = sorted(paths, key=lambda p: p[-1])
        parent_path = paths[0][:-1]
        if not parent_path:
            return
        parent_children = self.get_parent_children(paths[0])
        if not parent_children:
            return
        if [path[-1] for path in paths] != list(range(paths[0][-1], paths[0][-1] + len(paths))):
            messagebox.showinfo("안내", "연속된 스텝만 내어쓰기 할 수 있습니다.")
            return
        grand_children = self.get_parent_children(parent_path)
        insert_index = parent_path[-1] + 1 if parent_path else len(grand_children)
        moved = [parent_children[idx] for idx in [path[-1] for path in paths]]
        for idx in sorted([path[-1] for path in paths], reverse=True):
            parent_children.pop(idx)
        for offset, step in enumerate(moved):
            grand_children.insert(insert_index + offset, step)
        base_path = parent_path[:-1]
        new_paths = [
            (base_path + [insert_index + offset]) if base_path else [insert_index + offset]
            for offset in range(len(moved))
        ]
        self.refresh_steps()
        self.select_paths(new_paths)

    def clear_steps(self):
        children = self.get_active_children()
        if not children:
            return
        if messagebox.askyesno("확인", "현재 범위의 모든 스텝을 삭제할까요?"):
            children.clear()
            self.refresh_steps()

    def edit_selected_step(self):
        path = self.get_selected_path()
        if path is None:
            return
        step = self.get_step_by_path(path)
        if not step:
            return
        if step.get("type") == "block":
            if step.get("block_type") == "root":
                messagebox.showinfo("안내", "루트 블록은 편집할 수 없습니다.")
                return
            dlg = BlockDialog(self, block=step)
            self.wait_window(dlg)
            if not dlg.result:
                return
            result = dlg.result
            step["block_type"] = result["block_type"]
            step["meta"] = result.get("meta", {})
            step["schedule"] = self.normalize_schedule(result.get("schedule"))
            step["settings"] = result.get("settings") or {}
        else:
            fdef = copy.deepcopy(CATALOG_BY_NAME.get(step.get("name")))
            if not fdef:
                messagebox.showerror("오류", f"정의되지 않은 함수: {step.get('name')}")
                return
            self.resolve_dynamic_choices(fdef)
            dlg = ArgDialog(self, fdef, preset=step.get("args"), schedule=step.get("schedule"),
                            settings=step.get("settings"), allow_schedule=True, allow_settings=True)
            self.wait_window(dlg)
            if not dlg.result:
                return
            result = dlg.result
            step["args"] = result.get("args", {})
            step["schedule"] = self.normalize_schedule(result.get("schedule"))
            step["settings"] = result.get("settings") or {}
        self.refresh_steps()
        self.select_path(path)

    # ---------- 함수/전역 설정 ----------
    def get_current_function_index(self) -> int | None:
        label = self.var_scope.get()
        for kind, idx, lbl in getattr(self, "scope_options", []):
            if lbl == label and kind == "function":
                return idx
        return None

    def add_local_function(self):
        dlg = FunctionDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        data = dlg.result
        if any(fn.get("name") == data["name"] for fn in self.functions):
            messagebox.showerror("오류", "동일한 이름의 함수가 이미 존재합니다.")
            return
        func = {
            "name": data["name"],
            "params": data.get("params", []),
            "description": data.get("description", ""),
            "settings": data.get("settings", {}),
            "body": self._make_root_block(),
        }
        self.functions.append(func)
        self.update_scope_options()
        self.populate_func_tree()
        target_label = f"함수: {func['name']}"
        self.var_scope.set(target_label)
        if hasattr(self, "cb_scope"):
            self.cb_scope.set(target_label)
        self.refresh_steps()
        self.set_status(f"함수 추가됨: {func['name']}")

    def configure_local_function(self):
        idx = self.get_current_function_index()
        if idx is None:
            messagebox.showinfo("안내", "편집할 함수를 범위에서 선택하세요.")
            return
        func = self.functions[idx]
        dlg = FunctionDialog(self, func)
        self.wait_window(dlg)
        if not dlg.result:
            return
        data = dlg.result
        new_name = data["name"]
        if new_name != func["name"] and any(i != idx and f.get("name") == new_name for i, f in enumerate(self.functions)):
            messagebox.showerror("오류", "동일한 이름의 함수가 이미 존재합니다.")
            return
        old_name = func["name"]
        func["name"] = new_name
        func["params"] = data.get("params", [])
        func["description"] = data.get("description", "")
        func["settings"] = data.get("settings", {})
        if new_name != old_name:
            self.replace_function_references(old_name, new_name)
        self.update_scope_options()
        self.populate_func_tree()
        new_label = f"함수: {func['name']}"
        self.var_scope.set(new_label)
        if hasattr(self, "cb_scope"):
            self.cb_scope.set(new_label)
        self.refresh_steps()
        self.set_status(f"함수 업데이트: {func['name']}")

    def remove_local_function(self):
        idx = self.get_current_function_index()
        if idx is None:
            messagebox.showinfo("안내", "삭제할 함수를 범위에서 선택하세요.")
            return
        func = self.functions[idx]
        if not messagebox.askyesno("확인", f"함수 '{func['name']}'를 삭제할까요?"):
            return
        old_name = func["name"]
        del self.functions[idx]
        self.replace_function_references(old_name, None)
        self.update_scope_options()
        self.populate_func_tree()
        if getattr(self, "scope_options", []):
            first_label = self.scope_options[0][2]
            self.var_scope.set(first_label)
            if hasattr(self, "cb_scope"):
                self.cb_scope.set(first_label)
        else:
            self.var_scope.set("")
            if hasattr(self, "cb_scope"):
                self.cb_scope.set("")
        self.refresh_steps()
        self.set_status(f"함수 삭제됨: {old_name}")

    def replace_function_references(self, old: str, new: str | None):
        def visit(container: list[dict]):
            for st in container:
                if st.get("type") == "action" and st.get("name") == "__CALL_USER_FUNCTION__":
                    if st.get("args", {}).get("func") == old:
                        st.setdefault("args", {})["func"] = new or ""
                if st.get("type") == "block":
                    visit(st.get("children", []))

        visit(self.root_block.get("children", []))
        for fn in self.functions:
            body = fn.setdefault("body", self._make_root_block())
            visit(body.get("children", []))

    def open_global_settings(self):
        dlg = GlobalSettingsDialog(self, self.global_settings)
        self.wait_window(dlg)
        if not dlg.result:
            return
        result = dlg.result
        default_schedule = self.sanitize_schedule_dict(result.get("default_schedule"))
        self.global_settings = {
            "default_schedule": default_schedule,
            "prelude": result.get("prelude", ""),
            "notes": result.get("notes", ""),
            "custom": result.get("custom", {}),
        }
        self.refresh_steps()
        self.update_preview()

    # ---------- 저장/불러오기/내보내기 ----------
    def save_project(self):
        data = {
            "trigger": {
                "event": self.var_trigger_event.get(),
                "arg": self.var_trigger_arg.get(),
                "enable_primary": self.var_enable_primary.get(),
            },
            "global_settings": self.global_settings,
            "root": self.root_block,
            "functions": self.functions,
        }
        path = filedialog.asksaveasfilename(title="프로젝트 저장", defaultextension=".json",
                                            filetypes=[["JSON","*.json"],["All Files","*.*"]])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("저장됨", f"프로젝트 저장: {path}")

    def load_project(self):
        path = filedialog.askopenfilename(title="프로젝트 불러오기",
                                          filetypes=[["JSON","*.json"],["All Files","*.*"]])
        if not path:
            return
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

            loaded_global = data.get("global_settings")
            if isinstance(loaded_global, dict):
                self.global_settings = {
                    "default_schedule": self.sanitize_schedule_dict(loaded_global.get("default_schedule")),
                    "prelude": loaded_global.get("prelude", ""),
                    "notes": loaded_global.get("notes", ""),
                    "custom": loaded_global.get("custom", {}),
                }
            else:
                self.global_settings = {
                    "default_schedule": self.sanitize_schedule_dict({}),
                    "prelude": "",
                    "notes": "",
                    "custom": {},
                }

            raw_root = data.get("root")
            if isinstance(raw_root, dict):
                self.root_block = self.migrate_step(raw_root)
                self.root_block["block_type"] = "root"
            else:
                self.root_block = self._make_root_block()
                for st in data.get("steps", []):
                    self.root_block.setdefault("children", []).append(self.migrate_step(st))

            self.functions = []
            for fn_data in data.get("functions", []):
                func = {
                    "name": fn_data.get("name", f"Function{len(self.functions)+1}"),
                    "params": fn_data.get("params", []),
                    "description": fn_data.get("description", ""),
                    "settings": fn_data.get("settings", {}),
                    "body": self._make_root_block(),
                }
                body_data = fn_data.get("body")
                if isinstance(body_data, dict):
                    func["body"] = self.migrate_step(body_data)
                    func["body"]["block_type"] = "root"
                elif isinstance(body_data, list):
                    func["body"]["children"] = [self.migrate_step(st) for st in body_data]
                elif isinstance(fn_data.get("steps"), list):
                    func["body"]["children"] = [self.migrate_step(st) for st in fn_data.get("steps", [])]
                self.functions.append(func)

            self.update_scope_options()
            self.populate_func_tree()
            self.refresh_event_combobox(reset_arg=True)
            self.refresh_steps()
            self.update_preview()
            messagebox.showinfo("완료", f"불러오기 성공: {path}")
        except Exception as e:
            messagebox.showerror("불러오기 실패", str(e))

    def export_lua(self):
        has_steps = bool(self.root_block.get("children")) or any(
            (fn.get("body") or {}).get("children") for fn in self.functions
        )
        if not has_steps:
            if not messagebox.askyesno("확인", "스텝이 비어 있습니다. 그래도 내보낼까요?"):
                return
        path = filedialog.asksaveasfilename(title="Lua 내보내기", defaultextension=".lua",
                                            filetypes=[["Lua","*.lua"],["All Files","*.*"]])
        if not path:
            return
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
        notes = self.global_settings.get("notes")
        if isinstance(notes, str) and notes.strip():
            for line in notes.strip().splitlines():
                lines.append(f"-- {line}")
        if self.var_enable_primary.get():
            lines.append("EnablePrimaryMouseButtonEvents(true)")
        custom = self.global_settings.get("custom")
        if isinstance(custom, dict) and custom:
            lines.append("-- 전역 설정")
            for key, value in custom.items():
                lines.append(f"--   {key}: {value}")
        prelude = self.global_settings.get("prelude")
        if isinstance(prelude, str) and prelude.strip():
            lines.extend(prelude.splitlines())
        lines.append("")

        for fn in self.functions:
            name = fn.get("name", "")
            if not name:
                continue
            params = ", ".join(fn.get("params", []))
            lines.append(f"local function {name}({params})")
            body = fn.get("body") or self._make_root_block()
            body_lines = self.emit_steps_to_lua(body.get("children", []), "  ")
            if not body_lines:
                body_lines = ["  -- (no steps)"]
            lines.extend(body_lines)
            lines.append("end")
            lines.append("")

        lines.append("function OnEvent(event, arg)")
        ev = self.var_trigger_event.get()
        ar = self.var_trigger_arg.get()
        cond = []
        if ev:
            cond.append(f"event == \"{ev}\"")
        if ar != -1:
            cond.append(f"arg == {ar}")
        if cond:
            lines.append(f"  if {' and '.join(cond)} then")
            indent = "    "
        else:
            indent = "  "
        main_lines = self.emit_steps_to_lua(self.root_block.get("children", []), indent)
        if not main_lines:
            main_lines = [indent + "-- (no steps)"]
        lines.extend(main_lines)
        if cond:
            lines.append("  end")
        lines.append("end")
        return "\n".join(lines) + "\n"

    def emit_steps_to_lua(self, steps: list, indent: str) -> list[str]:
        lines: list[str] = []
        for step in steps:
            lines.extend(self.emit_step_to_lua(step, indent))
        return lines

    def emit_step_to_lua(self, step: dict, indent: str) -> list[str]:
        lines: list[str] = []
        settings = step.get("settings") or {}
        note = settings.get("note") or settings.get("notes")
        if isinstance(note, str) and note.strip():
            for line in note.strip().splitlines():
                lines.append(indent + f"-- {line}")
        for key, value in settings.items():
            if key in ("note", "notes", "pre_lua", "post_lua"):
                continue
            lines.append(indent + f"-- {key}: {value}")
        pre_lua = settings.get("pre_lua")
        if isinstance(pre_lua, str) and pre_lua.strip():
            for line in pre_lua.splitlines():
                lines.append(indent + line)

        def body(inner_indent: str) -> list[str]:
            return self._emit_step_core_to_lua(step, inner_indent)

        lines.extend(self.wrap_with_schedule(step.get("schedule"), indent, body))

        post_lua = settings.get("post_lua")
        if isinstance(post_lua, str) and post_lua.strip():
            for line in post_lua.splitlines():
                lines.append(indent + line)
        return lines

    def _emit_step_core_to_lua(self, step: dict, indent: str) -> list[str]:
        st_type = step.get("type")
        if st_type == "action":
            return self.emit_action_to_lua(step, indent)
        if st_type == "block":
            return self.emit_block_to_lua(step, indent)
        return [indent + f"-- 알 수 없는 스텝 타입: {st_type}"]

    def emit_action_to_lua(self, step: dict, indent: str) -> list[str]:
        name = step.get("name")
        args = step.get("args", {}) or {}
        if name == "__CALL_USER_FUNCTION__":
            target = str(args.get("func", "")).strip()
            expr = str(args.get("arg_expr", "")).strip()
            if not target:
                return [indent + "-- 사용자 함수 호출 대상 없음"]
            call = f"{target}({expr})" if expr else f"{target}()"
            return [indent + call]
        fdef = CATALOG_BY_NAME.get(name)
        if not fdef:
            return [indent + f"-- 정의 누락: {name}"]
        if name == "MoveMouseTo":
            x_px = int(args.get("x", 0)); y_px = int(args.get("y", 0))
            x_abs = round(max(0, min(self.screen_w - 1, x_px)) * 65535 / max(1, self.screen_w - 1))
            y_abs = round(max(0, min(self.screen_h - 1, y_px)) * 65535 / max(1, self.screen_h - 1))
            return [indent + f"MoveMouseTo({x_abs}, {y_abs})  -- ({x_px}px, {y_px}px)"]
        if name == "MoveMouseToVirtual":
            x_px = int(args.get("x", 0)); y_px = int(args.get("y", 0))
            x_abs = round(max(0, min(self.screen_w - 1, x_px)) * 65535 / max(1, self.screen_w - 1))
            y_abs = round(max(0, min(self.screen_h - 1, y_px)) * 65535 / max(1, self.screen_h - 1))
            return [indent + f"MoveMouseToVirtual({x_abs}, {y_abs})  -- ({x_px}px, {y_px}px)"]
        call = format_call(fdef["call"], args)
        return [indent + call]

    def emit_block_to_lua(self, step: dict, indent: str) -> list[str]:
        block_type = step.get("block_type")
        meta = step.get("meta", {}) or {}
        label = meta.get("label") or meta.get("description")
        lines: list[str] = []
        if label:
            lines.append(indent + f"-- {label}")
        children = step.get("children", [])
        if block_type == "repeat":
            count = max(1, int(meta.get("count", 1) or 1))
            loop_var = meta.get("var_name") or meta.get("loop_var") or self.normalize_schedule(step.get("schedule")).get("loop_var", "i")
            lines.append(indent + f"for {loop_var}=1,{count} do")
            lines.extend(self.emit_steps_to_lua(children, indent + "  "))
            lines.append(indent + "end")
            return lines
        if block_type == "while":
            condition = meta.get("condition", "true") or "true"
            lines.append(indent + f"while {condition} do")
            lines.extend(self.emit_steps_to_lua(children, indent + "  "))
            lines.append(indent + "end")
            return lines
        if block_type == "if":
            condition = meta.get("condition", "true") or "true"
            lines.append(indent + f"if {condition} then")
            lines.extend(self.emit_steps_to_lua(children, indent + "  "))
            lines.append(indent + "end")
            return lines
        if block_type == "root":
            return self.emit_steps_to_lua(children, indent)
        lines.append(indent + f"-- 지원되지 않는 블록 타입: {block_type}")
        lines.extend(self.emit_steps_to_lua(children, indent + "  "))
        return lines

    def wrap_with_schedule(self, schedule: dict | None, indent: str, body: Callable[[str], list[str]]) -> list[str]:
        sch = self.normalize_schedule(schedule)
        lines: list[str] = []
        if sch.get("start_delay"):
            lines.append(indent + f"Sleep({sch['start_delay']})")
        repeat = sch.get("repeat", 1)
        interval = sch.get("interval", 0)
        cooldown = sch.get("cooldown", 0)
        loop_var = sch.get("loop_var", "i") or "i"
        if repeat > 1 or interval > 0:
            lines.append(indent + f"for {loop_var}=1,{repeat} do")
            inner_indent = indent + "  "
            lines.extend(body(inner_indent))
            if interval > 0:
                if repeat > 1:
                    lines.append(inner_indent + f"if {loop_var} < {repeat} then Sleep({interval}) end")
                else:
                    lines.append(inner_indent + f"Sleep({interval})")
            lines.append(indent + "end")
        else:
            lines.extend(body(indent))
        if cooldown > 0:
            lines.append(indent + f"Sleep({cooldown})")
        return lines

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
        step = self.make_action_step("Sleep", args={"ms": 10})
        new_path = self.insert_step_after(self.get_selected_path(), step)
        self.refresh_steps()
        self.select_path(new_path)
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
        app = ScriptBuilderApp()
        app.root_block["children"] = [
            app.make_action_step("MoveMouseTo", {"x": app.screen_w // 2, "y": app.screen_h // 2}),
            app.make_action_step("Sleep", {"ms": 10}),
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
