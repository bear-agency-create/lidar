#!/usr/bin/env python3
"""Вкладный Tk-интерфейс оператора: Состояние / Логи / Тесты / Карта."""

from __future__ import annotations

import json
import math
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = os.environ.get("ROBOT_API", "http://127.0.0.1:8765").rstrip("/")

_YES = "да"
_NO = "нет"


def http_json(method: str, path: str, body: dict | None = None, timeout: float = 4.0) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def http_err_text(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        try:
            return json.loads(exc.read().decode()).get("error") or str(exc)
        except Exception:  # noqa: BLE001
            return str(exc)
    return str(exc)


def _da(val: Any) -> str:
    """да/нет from truthy value."""
    return _YES if val else _NO


def _nav_ru(status: Any) -> str:
    s = str(status or "-")
    table = {
        "idle": "ожидание",
        "running": "едет",
        "paused": "пауза",
        "done": "готово",
        "error": "ошибка",
        "planning": "планирование",
        "failed": "сбой",
        "stopped": "остановлен",
        "None": "нет",
        "none": "нет",
    }
    return table.get(s, s)


def _mission_ru(status: Any) -> str:
    s = str(status or "-")
    table = {
        "idle": "ожидание",
        "running": "выполняется",
        "done": "завершена",
        "error": "ошибка",
        "paused": "пауза",
        "planning": "планирование",
        "None": "нет",
        "none": "нет",
    }
    return table.get(s, s)


def _grade_ru(grade: Any) -> str:
    g = str(grade or "?")
    names = {"A": "отлично", "B": "хорошо", "C": "средне", "D": "слабо"}
    return f"{g} ({names.get(g, 'оценка')})"


class OperatorGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Оператор робота — {API}")
        self.geometry("1360x860")
        self.minsize(1100, 700)
        self.configure(bg="#18222e")

        self.snap: dict[str, Any] = {}
        self.health: dict[str, Any] = {}
        self.analysis: dict[str, Any] = {}
        self.waypoints: list[dict[str, Any]] = []
        self._alive = True
        self.scale = 16.0
        self.ox = 0.0
        self.oy = 0.0
        self.drag = None
        self.click_add = tk.BooleanVar(value=True)
        self.log_filter = tk.StringVar(value="")
        self.test_out = tk.StringVar(value="Готово к тестам.")

        self._build()
        self.after(200, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background="#18222e")
        style.configure("TNotebook.Tab", padding=[14, 8], font=("Segoe UI", 10, "bold"))
        style.configure("TFrame", background="#1e2a38")
        style.configure("TLabel", background="#1e2a38", foreground="#d7e6f5")
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#7ec8ff")

        top = tk.Frame(self, bg="#18222e")
        top.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(top, text="ОПЕРАТОР", fg="#7ec8ff", bg="#18222e", font=("Segoe UI", 16, "bold")).pack(
            side=tk.LEFT
        )
        self.banner = tk.Label(
            top, text="подключение…", fg="#cfe3f5", bg="#18222e", font=("Consolas", 10)
        )
        self.banner.pack(side=tk.LEFT, padx=16)
        tk.Button(top, text="Обновить всё", command=self._refresh_all).pack(side=tk.RIGHT, padx=4)
        tk.Button(top, text="СТОП", fg="#b00020", command=self._stop).pack(side=tk.RIGHT, padx=4)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.tab_state = ttk.Frame(self.nb)
        self.tab_logs = ttk.Frame(self.nb)
        self.tab_tests = ttk.Frame(self.nb)
        self.tab_map = ttk.Frame(self.nb)
        self.nb.add(self.tab_state, text="  Состояние  ")
        self.nb.add(self.tab_logs, text="  Логи  ")
        self.nb.add(self.tab_tests, text="  Тесты  ")
        self.nb.add(self.tab_map, text="  Карта / Миссия  ")

        self._build_state()
        self._build_logs()
        self._build_tests()
        self._build_map()

    # ---- State tab ----
    def _build_state(self) -> None:
        left = ttk.Frame(self.tab_state)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        right = ttk.Frame(self.tab_state)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        ttk.Label(left, text="Живое состояние", style="Header.TLabel").pack(anchor="w")
        self.state_live = tk.Text(left, height=18, bg="#121a24", fg="#d7e6f5", font=("Consolas", 10), wrap="word")
        self.state_live.pack(fill=tk.BOTH, expand=True, pady=6)

        ttk.Label(right, text="Здоровье системы (Pi)", style="Header.TLabel").pack(anchor="w")
        self.state_health = tk.Text(right, height=10, bg="#121a24", fg="#d7e6f5", font=("Consolas", 10), wrap="word")
        self.state_health.pack(fill=tk.BOTH, expand=True, pady=6)

        ttk.Label(right, text="Анализ карты / навигации", style="Header.TLabel").pack(anchor="w")
        self.state_analyze = tk.Text(right, height=12, bg="#121a24", fg="#d7e6f5", font=("Consolas", 10), wrap="word")
        self.state_analyze.pack(fill=tk.BOTH, expand=True, pady=6)

        row = ttk.Frame(left)
        row.pack(fill=tk.X, pady=4)
        tk.Button(row, text="Здоровье", command=self._load_health).pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="Анализ карты", command=self._load_analyze).pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="Сохранить карту", command=lambda: self._api_post("/api/save", {})).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(row, text="Очистить карту", command=self._clear_map).pack(side=tk.LEFT, padx=2)

    # ---- Logs tab ----
    def _build_logs(self) -> None:
        bar = ttk.Frame(self.tab_logs)
        bar.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(bar, text="Фильтр:").pack(side=tk.LEFT)
        tk.Entry(bar, textvariable=self.log_filter, width=28).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="Обновить логи", command=self._load_logs).pack(side=tk.LEFT, padx=4)
        self.logs_box = tk.Text(self.tab_logs, bg="#0d131b", fg="#b7c7d6", font=("Consolas", 9), wrap="none")
        self.logs_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        ys = tk.Scrollbar(self.logs_box, orient="vertical", command=self.logs_box.yview)
        self.logs_box.configure(yscrollcommand=ys.set)

    # ---- Tests tab ----
    def _build_tests(self) -> None:
        wrap = ttk.Frame(self.tab_tests)
        wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        ttk.Label(wrap, text="Диагностика и проверки", style="Header.TLabel").pack(anchor="w")

        grid = ttk.Frame(wrap)
        grid.pack(fill=tk.X, pady=10)
        tests = [
            ("Пинг API / скан", self._test_scan),
            ("Здоровье процессов/USB", self._test_health),
            ("Анализ карты", self._test_analyze),
            ("Мотор ВПЕРЁД 1.2с", lambda: self._test_motor(0.18, 0, 0, 1.2, "ВПЕРЁД")),
            ("Мотор НАЗАД 1.2с", lambda: self._test_motor(-0.18, 0, 0, 1.2, "НАЗАД")),
            ("Мотор СТРЕЙФ Л", lambda: self._test_motor(0, 0.18, 0, 1.0, "СТРЕЙФ_Л")),
            ("Мотор СТРЕЙФ П", lambda: self._test_motor(0, -0.18, 0, 1.0, "СТРЕЙФ_П")),
            ("Мотор ПОВОРОТ", lambda: self._test_motor(0, 0, 0.45, 1.0, "ПОВОРОТ")),
            ("СТОП", self._stop),
            ("План демо-миссии", self._test_plan_demo),
        ]
        for i, (label, cmd) in enumerate(tests):
            tk.Button(grid, text=label, width=22, command=cmd).grid(
                row=i // 3, column=i % 3, padx=6, pady=6, sticky="ew"
            )

        ttk.Label(wrap, text="Результат теста", style="Header.TLabel").pack(anchor="w", pady=(12, 4))
        self.test_box = tk.Text(wrap, height=18, bg="#121a24", fg="#e8f0f8", font=("Consolas", 10), wrap="word")
        self.test_box.pack(fill=tk.BOTH, expand=True)
        self._set_test(self.test_out.get())

    # ---- Map tab ----
    def _build_map(self) -> None:
        left = ttk.Frame(self.tab_map)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)
        mid = ttk.Frame(self.tab_map)
        mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=8)
        right = ttk.Frame(self.tab_map)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=8, pady=8)

        ttk.Label(left, text="Телеуправление", style="Header.TLabel").pack(anchor="w")
        pad = ttk.Frame(left)
        pad.pack(pady=6)
        for t, fn in [
            ("↑", lambda: self._cmd(0.2, 0, 0)),
            ("←", lambda: self._cmd(0, 0.2, 0)),
            ("СТОП", self._stop),
            ("→", lambda: self._cmd(0, -0.2, 0)),
            ("↓", lambda: self._cmd(-0.2, 0, 0)),
            ("↺", lambda: self._cmd(0, 0, 0.5)),
            ("↻", lambda: self._cmd(0, 0, -0.5)),
        ]:
            tk.Button(pad, text=t, width=5, command=fn).pack(side=tk.LEFT, padx=2)

        ttk.Label(left, text="Легенда карты", style="Header.TLabel").pack(anchor="w", pady=(12, 4))
        legend = (
            "Вид сверху\n"
            "• серые точки — стены\n"
            "• зелёный — робот\n"
            "  (стрелка = куда смотрит)\n"
            "• жёлтые круги — точки маршрута\n"
            "• голубая линия — путь\n"
            "• красный — текущая цель\n"
            "• сетка — 1 метр\n"
            "\n"
            "Колесо мыши — масштаб\n"
            "Перетаскивание — сдвиг\n"
            "Клик — добавить точку"
        )
        self.map_legend = tk.Text(
            left, width=36, height=14, bg="#121a24", fg="#c5d8ea", font=("Segoe UI", 9), wrap="word"
        )
        self.map_legend.pack(fill=tk.X, expand=False)
        self.map_legend.insert(tk.END, legend)
        self.map_legend.configure(state="disabled")

        ttk.Label(left, text="Анализ (кратко)", style="Header.TLabel").pack(anchor="w", pady=(12, 4))
        self.map_stats = tk.Text(left, width=36, height=12, bg="#121a24", fg="#d7e6f5", font=("Consolas", 9))
        self.map_stats.pack(fill=tk.Y, expand=False)

        self.canvas = tk.Canvas(mid, bg="#0b1017", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<MouseWheel>", lambda e: self._zoom(1.12 if e.delta > 0 else 1 / 1.12))

        ttk.Label(right, text="Миссия (приоритет ↑ = раньше)", style="Header.TLabel").pack(anchor="w")
        form = ttk.Frame(right)
        form.pack(fill=tk.X, pady=4)
        ttk.Label(form, text="x").grid(row=0, column=0)
        ttk.Label(form, text="y").grid(row=0, column=1)
        ttk.Label(form, text="приор.").grid(row=0, column=2)
        self.ex = tk.Entry(form, width=8)
        self.ey = tk.Entry(form, width=8)
        self.ep = tk.Entry(form, width=5)
        self.ex.grid(row=1, column=0, padx=2)
        self.ey.grid(row=1, column=1, padx=2)
        self.ep.grid(row=1, column=2, padx=2)
        self.ep.insert(0, "0")
        tk.Button(form, text="+", command=self._add_fields).grid(row=1, column=3, padx=4)
        self.wp_list = tk.Listbox(right, height=14, width=34, bg="#121a24", fg="#d7e6f5", font=("Consolas", 9))
        self.wp_list.pack(fill=tk.BOTH, expand=True, pady=4)
        row = ttk.Frame(right)
        row.pack(fill=tk.X, pady=4)
        tk.Button(row, text="Прио+", command=lambda: self._bump(1)).pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="Прио−", command=lambda: self._bump(-1)).pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="Удалить", command=self._del_wp).pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="Очистить", command=self._clear_wp).pack(side=tk.LEFT, padx=2)
        row2 = ttk.Frame(right)
        row2.pack(fill=tk.X, pady=6)
        tk.Button(row2, text="План", width=10, command=self._plan).pack(side=tk.LEFT, padx=2)
        tk.Button(row2, text="Старт", width=10, command=self._go).pack(side=tk.LEFT, padx=2)
        tk.Checkbutton(
            right,
            text="Клик по карте = точка",
            variable=self.click_add,
            bg="#1e2a38",
            fg="#d7e6f5",
            selectcolor="#121a24",
            activebackground="#1e2a38",
        ).pack(anchor="w", pady=6)

    # ---- helpers ----
    def _close(self) -> None:
        self._alive = False
        self.destroy()

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state="disabled")

    def _set_test(self, text: str) -> None:
        self.test_out.set(text)
        self.test_box.configure(state="normal")
        self.test_box.delete("1.0", tk.END)
        self.test_box.insert(tk.END, text)
        self.test_box.configure(state="disabled")

    def _api_post(self, path: str, body: dict) -> None:
        try:
            http_json("POST", path, body)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Ошибка API", http_err_text(exc))

    def _cmd(self, vx: float, vy: float, w: float) -> None:
        self._api_post("/api/cmd", {"vx": vx, "vy": vy, "w": w})

    def _stop(self) -> None:
        self._api_post("/api/cmd/stop", {})

    def _clear_map(self) -> None:
        if messagebox.askyesno("Очистка карты", "Сбросить карту на роботе?"):
            self._api_post("/api/clear", {})

    def _refresh_all(self) -> None:
        self._load_health()
        self._load_analyze()
        self._load_logs()

    def _fmt_live(self) -> str:
        s = self.snap
        p = s.get("pose") or {}
        m = s.get("mission") or {}
        cur = (m.get("current") or {}).get("label") or "—"
        err = s.get("error") or "нет"
        path_n = len(s.get("path") or [])
        goal = s.get("goal")
        if isinstance(goal, (list, tuple)) and len(goal) >= 2:
            goal_s = f"x={float(goal[0]):+.2f} м, y={float(goal[1]):+.2f} м"
        else:
            goal_s = "нет"
        saved = s.get("saved_ago")
        saved_s = f"{saved} с назад" if saved is not None else "—"
        return "\n".join(
            [
                f"Адрес API: {API}",
                f"Лидар: {_da(s.get('ok'))}",
                f"Одометрия: {_da(s.get('odom_ok'))}",
                f"Картографирование: {_da(s.get('mapping'))}  "
                f"(оценка совпадения {float(s.get('score') or 0):.2f})",
                f"Карта заморожена: {_da(s.get('frozen'))}",
                f"Данные устарели: {_da(s.get('stale'))}",
                f"Навигация: {_nav_ru(s.get('nav_status'))}",
                f"Текущая цель: {goal_s}",
                f"Точек в пути: {path_n}",
                f"Поза: x={float(p.get('x', 0)):+.3f} м, "
                f"y={float(p.get('y', 0)):+.3f} м, "
                f"курс={float(p.get('yaw', 0)):+.3f} рад",
                f"Миссия: {_mission_ru(m.get('status'))}  "
                f"{m.get('index', 0)}/{m.get('total', 0)}",
                f"Текущая точка маршрута: {cur}",
                f"Ошибка: {err}",
                f"Карта сохранена: {saved_s}",
                f"Временные препятствия: {s.get('temp_hits') or 0}",
            ]
        )

    def _fmt_health(self) -> str:
        h = self.health
        if not h:
            return "Нажми «Здоровье», чтобы загрузить данные."
        procs = h.get("processes") or {}
        dev = h.get("devices") or {}
        logs = h.get("logs") or {}
        mf = h.get("map_file") or {}
        age = mf.get("age_sec")
        age_s = f"{age:.0f} с" if isinstance(age, (int, float)) else "—"
        lines = [
            "Процессы на Pi:",
            f"  main.py: {_da(procs.get('main'))}",
            f"  драйв/энкодеры: {_da(procs.get('drive_encoders'))}",
            f"  лидар (cspc_lidar): {_da(procs.get('lidar'))}",
            "",
            "Устройства:",
            f"  ttyLIDAR → {dev.get('ttyLIDAR_target') or 'нет'}",
            f"  ttyMEGA  → {dev.get('ttyMEGA_target') or 'нет'}",
            f"  USB0={_da(dev.get('ttyUSB0'))}  USB1={_da(dev.get('ttyUSB1'))}",
            "",
            f"Размер лога: {logs.get('bytes') or 0} байт",
            f"Файл карты: {mf.get('bytes') or 0} байт, возраст {age_s}",
            "",
            "Подсказки:",
        ]
        for hint in h.get("hints") or []:
            lines.append(f" • {hint}")
        listing = h.get("process_listing") or []
        if listing:
            lines.append("")
            lines.append("Список процессов:")
            for row in listing:
                lines.append(f"  {row}")
        return "\n".join(lines)

    def _fmt_analyze(self) -> str:
        a = self.analysis
        if not a:
            return "Нажми «Анализ карты», чтобы загрузить данные."
        q = a.get("quality") or {}
        mp = a.get("map") or {}
        nav = a.get("nav") or {}
        sens = a.get("sensors") or {}
        span = mp.get("span") or {}
        wall = mp.get("nearest_wall_m")
        wall_s = f"{wall} м" if wall is not None else "—"
        sx = span.get("x_m")
        sy = span.get("y_m")
        area = span.get("area_m2")
        if sx is not None and sy is not None:
            span_s = f"{sx:.2f} × {sy:.2f} м"
            if area is not None:
                span_s += f" (площадь ≈ {area:.1f} м²)"
        else:
            span_s = "ещё нет"
        lines = [
            f"Качество карты: {_grade_ru(q.get('grade'))}, балл {q.get('score')}",
            f"Покрытие: {mp.get('coverage_pct')}%  "
            f"(плотных клеток {mp.get('solid_cells')}, слабых {mp.get('weak_cells')})",
            f"Ближайшая стена: {wall_s}",
            f"Размер зоны: {span_s}",
            f"Длина пути: {nav.get('path_length_m')} м  "
            f"Навигация: {_nav_ru(nav.get('status'))}",
            f"Лидар: {_da(sens.get('scan_ok'))}  "
            f"Одометрия: {_da(sens.get('odom_ok'))}  "
            f"Оценка совпадения: {sens.get('score')}",
            "",
            "Заметки:",
        ]
        for n in q.get("notes") or []:
            lines.append(f" • {n}")
        lines.append("")
        lines.append("Рекомендации:")
        for n in a.get("recommendations") or []:
            lines.append(f" → {n}")
        return "\n".join(lines)

    def _load_health(self) -> None:
        try:
            self.health = http_json("GET", "/api/health")
            self._set_text(self.state_health, self._fmt_health())
        except Exception as exc:  # noqa: BLE001
            self._set_text(self.state_health, f"Ошибка здоровья: {http_err_text(exc)}")

    def _load_analyze(self) -> None:
        try:
            self.analysis = http_json("GET", "/api/analyze")
            text = self._fmt_analyze()
            self._set_text(self.state_analyze, text)
            self._set_text(self.map_stats, text)
        except Exception as exc:  # noqa: BLE001
            err = f"Ошибка анализа: {http_err_text(exc)}"
            self._set_text(self.state_analyze, err)
            self._set_text(self.map_stats, err)

    def _load_logs(self) -> None:
        try:
            data = http_json("GET", "/api/logs?n=250")
            lines = [str(x) for x in (data.get("lines") or [])]
            flt = self.log_filter.get().strip().lower()
            if flt:
                lines = [ln for ln in lines if flt in ln.lower()]
            self.logs_box.configure(state="normal")
            self.logs_box.delete("1.0", tk.END)
            self.logs_box.insert(tk.END, "\n".join(lines))
            self.logs_box.see(tk.END)
            self.logs_box.configure(state="disabled")
        except Exception as exc:  # noqa: BLE001
            self.logs_box.configure(state="normal")
            self.logs_box.delete("1.0", tk.END)
            self.logs_box.insert(tk.END, f"Ошибка логов: {http_err_text(exc)}")
            self.logs_box.configure(state="disabled")

    # tests
    def _test_scan(self) -> None:
        try:
            s = http_json("GET", "/api/scan")
            self._set_test(
                "Скан API — успешно\n"
                f"Лидар: {_da(s.get('ok'))}\n"
                f"Одометрия: {_da(s.get('odom_ok'))}\n"
                f"Навигация: {_nav_ru(s.get('nav_status'))}\n"
                f"Точек скана: {len(s.get('points') or [])}\n"
                f"Клеток карты: {len((s.get('map') or {}).get('cells') or [])}"
            )
        except Exception as exc:  # noqa: BLE001
            self._set_test(f"Скан не удался: {http_err_text(exc)}")

    def _test_health(self) -> None:
        try:
            self.health = http_json("GET", "/api/health")
            self._set_test(self._fmt_health())
            self._set_text(self.state_health, self._fmt_health())
        except Exception as exc:  # noqa: BLE001
            self._set_test(f"Здоровье не удалось: {http_err_text(exc)}")

    def _test_analyze(self) -> None:
        try:
            self.analysis = http_json("GET", "/api/analyze")
            self._set_test(self._fmt_analyze())
            self._set_text(self.state_analyze, self._fmt_analyze())
            self._set_text(self.map_stats, self._fmt_analyze())
        except Exception as exc:  # noqa: BLE001
            self._set_test(f"Анализ не удался: {http_err_text(exc)}")

    def _test_motor(self, vx: float, vy: float, w: float, sec: float, label: str) -> None:
        def work() -> None:
            try:
                http_json("POST", "/api/cmd", {"vx": vx, "vy": vy, "w": w})
                time.sleep(sec)
                http_json("POST", "/api/cmd/stop", {})
                self.after(
                    0,
                    lambda: self._set_test(
                        f"Мотор «{label}» — ок ({sec} с)\nvx={vx} vy={vy} w={w}"
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                self.after(
                    0,
                    lambda: self._set_test(f"Мотор «{label}» — сбой: {http_err_text(exc)}"),
                )

        self._set_test(f"Мотор «{label}» — выполняется…")
        threading.Thread(target=work, daemon=True).start()

    def _test_plan_demo(self) -> None:
        pose = self.snap.get("pose") or {}
        x = float(pose.get("x", 0.0))
        y = float(pose.get("y", 0.0))
        wps = [
            {"x": x + 0.6, "y": y, "priority": 2, "label": "A"},
            {"x": x, "y": y + 0.6, "priority": 5, "label": "B-high"},
        ]
        try:
            res = http_json("POST", "/api/mission/plan", {"waypoints": wps})
            if res.get("ok"):
                self.snap["selected_path"] = res.get("path") or []
                self._draw()
                self._set_test(
                    "Демо-миссия запланирована.\n"
                    f"Длина пути: {res.get('path_len')}\n"
                    + json.dumps(res, ensure_ascii=False, indent=2)[:2000]
                )
            else:
                self._set_test(f"План не удался: {res.get('error', 'ошибка')}")
        except Exception as exc:  # noqa: BLE001
            self._set_test(f"План не удался: {http_err_text(exc)}")

    # mission / map
    def _ordered_waypoints(self) -> list[dict[str, Any]]:
        return sorted(self.waypoints, key=lambda w: (-int(w["priority"]), int(w["order"])))

    def _refresh_wp(self) -> None:
        self.wp_list.delete(0, tk.END)
        for n, wp in enumerate(self._ordered_waypoints(), start=1):
            self.wp_list.insert(
                tk.END,
                f"#{n}  приор.{wp['priority']:>2}  ({wp['x']:+.2f},{wp['y']:+.2f})  {wp['label']}",
            )

    def _add(self, x: float, y: float, p: int) -> None:
        i = len(self.waypoints)
        self.waypoints.append(
            {"x": x, "y": y, "priority": p, "order": i, "id": f"wp{i+1}", "label": f"P{i+1}"}
        )
        self._refresh_wp()
        self._draw()

    def _add_fields(self) -> None:
        try:
            self._add(float(self.ex.get()), float(self.ey.get()), int(self.ep.get() or "0"))
        except ValueError:
            messagebox.showerror("Точка маршрута", "Нужны числа: x, y и приоритет")

    def _selected_idx(self) -> int | None:
        sel = self.wp_list.curselection()
        if not sel:
            return None
        ordered = self._ordered_waypoints()
        return self.waypoints.index(ordered[int(sel[0])])

    def _bump(self, d: int) -> None:
        i = self._selected_idx()
        if i is None:
            return
        self.waypoints[i]["priority"] = int(self.waypoints[i]["priority"]) + d
        self._refresh_wp()
        self._draw()

    def _del_wp(self) -> None:
        i = self._selected_idx()
        if i is None:
            return
        self.waypoints.pop(i)
        for n, wp in enumerate(self.waypoints):
            wp["order"] = n
        self._refresh_wp()
        self._draw()

    def _clear_wp(self) -> None:
        self.waypoints.clear()
        self._refresh_wp()
        self._draw()

    def _plan(self) -> None:
        if not self.waypoints:
            return
        try:
            res = http_json("POST", "/api/mission/plan", {"waypoints": self.waypoints})
            if res.get("ok"):
                self.snap["selected_path"] = res.get("path") or []
                self._draw()
                messagebox.showinfo("План маршрута", f"Длина пути: {res.get('path_len')}")
            else:
                messagebox.showerror("План маршрута", res.get("error", "сбой"))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("План маршрута", http_err_text(exc))

    def _go(self) -> None:
        if not self.waypoints:
            return
        try:
            res = http_json("POST", "/api/mission", {"waypoints": self.waypoints, "start": True})
            if not res.get("ok"):
                messagebox.showerror("Старт миссии", res.get("error", "сбой"))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Старт миссии", http_err_text(exc))

    def _w2c(self, x: float, y: float) -> tuple[float, float]:
        w = self.canvas.winfo_width() or 800
        h = self.canvas.winfo_height() or 600
        return w / 2 + (x - self.ox) * self.scale, h / 2 - (y - self.oy) * self.scale

    def _c2w(self, cx: float, cy: float) -> tuple[float, float]:
        w = self.canvas.winfo_width() or 800
        h = self.canvas.winfo_height() or 600
        return self.ox + (cx - w / 2) / self.scale, self.oy - (cy - h / 2) / self.scale

    def _press(self, e) -> None:
        self.drag = (e.x, e.y, self.ox, self.oy, time.time())

    def _motion(self, e) -> None:
        if not self.drag:
            return
        x0, y0, ox, oy, _ = self.drag
        self.ox = ox - (e.x - x0) / self.scale
        self.oy = oy + (e.y - y0) / self.scale
        self._draw()

    def _release(self, e) -> None:
        if not self.drag:
            return
        x0, y0, _, _, t0 = self.drag
        self.drag = None
        if abs(e.x - x0) + abs(e.y - y0) < 5 and time.time() - t0 < 0.6 and self.click_add.get():
            x, y = self._c2w(e.x, e.y)
            try:
                p = int(self.ep.get() or "0")
            except ValueError:
                p = 0
            self._add(x, y, p)
            self.ex.delete(0, tk.END)
            self.ey.delete(0, tk.END)
            self.ex.insert(0, f"{x:.2f}")
            self.ey.insert(0, f"{y:.2f}")

    def _zoom(self, factor: float) -> None:
        self.scale = max(4.0, min(90.0, self.scale * factor))
        self._draw()

    def _draw_grid(self) -> None:
        """1 m world grid across the visible canvas."""
        c = self.canvas
        w = c.winfo_width() or 800
        h = c.winfo_height() or 600
        x0, y0 = self._c2w(0, h)
        x1, y1 = self._c2w(w, 0)
        xmin, xmax = min(x0, x1), max(x0, x1)
        ymin, ymax = min(y0, y1), max(y0, y1)
        gx0 = math.floor(xmin)
        gy0 = math.floor(ymin)
        gx1 = math.ceil(xmax)
        gy1 = math.ceil(ymax)
        for gx in range(gx0, gx1 + 1):
            a = self._w2c(float(gx), ymin)
            b = self._w2c(float(gx), ymax)
            color = "#1a2838" if gx % 5 else "#243448"
            c.create_line(a[0], a[1], b[0], b[1], fill=color, width=1)
        for gy in range(gy0, gy1 + 1):
            a = self._w2c(xmin, float(gy))
            b = self._w2c(xmax, float(gy))
            color = "#1a2838" if gy % 5 else "#243448"
            c.create_line(a[0], a[1], b[0], b[1], fill=color, width=1)

    def _draw_legend_overlay(self) -> None:
        """Compact Russian legend overlay, top-left on canvas."""
        c = self.canvas
        lines = [
            "Вид сверху",
            "серые = стены",
            "зелёный = робот",
            "жёлтые = точки маршрута",
            "голубая = путь",
            "красный = цель",
            "сетка = 1 м",
            "колесо = масштаб · тянуть = сдвиг · клик = точка",
        ]
        pad = 8
        line_h = 14
        box_w = 290
        box_h = pad * 2 + line_h * len(lines) + 4
        c.create_rectangle(6, 6, 6 + box_w, 6 + box_h, fill="#0d1520", outline="#3a5570", width=1)
        y = 6 + pad + 6
        for i, text in enumerate(lines):
            fill = "#7ec8ff" if i == 0 else "#c5d8ea"
            font = ("Segoe UI", 9, "bold") if i == 0 else ("Segoe UI", 8)
            c.create_text(6 + pad, y, text=text, fill=fill, font=font, anchor="w")
            y += line_h

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        self._draw_grid()

        m = self.snap.get("map") or {}
        cells = m.get("cells") or []
        origin = m.get("origin") or [0, 0]
        res = float(m.get("resolution") or 0.05)
        ox, oy = float(origin[0]), float(origin[1])
        # Downsample dense wall cells for readability when zoomed out
        step = 1
        if self.scale < 10:
            step = 3
        elif self.scale < 18:
            step = 2
        for i, cell in enumerate(cells):
            if step > 1 and (i % step) != 0:
                continue
            if len(cell) < 3 or float(cell[2]) < 1.0:
                continue
            x, y = self._w2c(ox + (int(cell[0]) + 0.5) * res, oy + (int(cell[1]) + 0.5) * res)
            s = max(1.5, self.scale * res * 0.9)
            c.create_rectangle(x - s / 2, y - s / 2, x + s / 2, y + s / 2, fill="#4a6a82", outline="")

        path = self.snap.get("path") or self.snap.get("selected_path") or []
        if len(path) >= 2:
            pts: list[float] = []
            for p in path:
                pts.extend(self._w2c(float(p[0]), float(p[1])))
            c.create_line(*pts, fill="#5ad1ff", width=3)

        for n, wp in enumerate(self._ordered_waypoints(), start=1):
            x, y = self._w2c(float(wp["x"]), float(wp["y"]))
            r = 11
            c.create_oval(x - r, y - r, x + r, y + r, fill="#ffb000", outline="white", width=2)
            c.create_text(x, y, text=str(n), fill="#1a1200", font=("Segoe UI", 10, "bold"))
            c.create_text(
                x,
                y - 18,
                text=f"точка {n}",
                fill="#ffe6a8",
                font=("Segoe UI", 8),
            )

        goal = self.snap.get("goal")
        if isinstance(goal, (list, tuple)) and len(goal) >= 2:
            x, y = self._w2c(float(goal[0]), float(goal[1]))
            c.create_oval(x - 14, y - 14, x + 14, y + 14, outline="#ff6b6b", width=3)
            c.create_text(x, y + 22, text="цель", fill="#ff8a8a", font=("Segoe UI", 8, "bold"))

        pose = self.snap.get("pose") or {}
        if pose:
            x, y = self._w2c(float(pose.get("x", 0)), float(pose.get("y", 0)))
            yaw = float(pose.get("yaw", 0))
            r = 12
            c.create_oval(x - r, y - r, x + r, y + r, fill="#4cff8f", outline="white", width=2)
            arrow = 28
            c.create_line(
                x,
                y,
                x + math.cos(yaw) * arrow,
                y - math.sin(yaw) * arrow,
                fill="#4cff8f",
                width=3,
                arrow=tk.LAST,
            )
            c.create_text(x, y + 22, text="РОБОТ", fill="#9dffc0", font=("Segoe UI", 9, "bold"))

        self._draw_legend_overlay()

    def _tick(self) -> None:
        if not self._alive:
            return

        def work() -> None:
            try:
                snap = http_json("GET", "/api/scan")
            except Exception as exc:  # noqa: BLE001
                snap = {"ok": False, "error": str(exc), "pose": {}, "mission": {}}
            self.after(0, lambda: self._apply(snap))

        threading.Thread(target=work, daemon=True).start()
        self.after(500, self._tick)

    def _apply(self, snap: dict[str, Any]) -> None:
        if not self._alive:
            return
        self.snap = snap
        pose = snap.get("pose") or {}
        if pose and abs(self.ox) < 1e-9 and abs(self.oy) < 1e-9:
            self.ox = float(pose.get("x", 0))
            self.oy = float(pose.get("y", 0))
        self._set_text(self.state_live, self._fmt_live())
        err = snap.get("error") or ""
        self.banner.config(
            text=(
                f"Навигация: {_nav_ru(snap.get('nav_status'))}  ·  "
                f"Одометрия: {_da(snap.get('odom_ok'))}  ·  "
                f"Лидар: {_da(snap.get('ok'))}"
                + (f"  ·  {err}" if err else "")
            )
        )
        self._draw()


def run() -> None:
    OperatorGUI().mainloop()


if __name__ == "__main__":
    run()
