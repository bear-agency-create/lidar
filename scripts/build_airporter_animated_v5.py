# -*- coding: utf-8 -*-
"""Build an animated, material-driven AirPorter presentation (RU + EN)."""
from __future__ import annotations

import os
from pathlib import Path

import win32com.client as win32
from win32com.client import constants as c

DESKTOP = Path(os.path.expanduser(r"~\Desktop"))
MATERIALS = DESKTOP / "материал для AirPorter"
LOGO = MATERIALS / "AIRPORTER_logo.png"
ROBOT = MATERIALS / "photo_2026-08-07_13-37-15.jpg"


def rgb(r: int, g: int, b: int) -> int:
    return r + (g << 8) + (b << 16)


# New identity: black technical-board + electric cyan.
BLACK = rgb(3, 8, 14)
DEEP = rgb(7, 18, 29)
PANEL = rgb(12, 30, 44)
PANEL2 = rgb(16, 42, 58)
CYAN = rgb(0, 190, 235)
BLUE = rgb(0, 116, 196)
ICE = rgb(193, 235, 246)
WHITE = rgb(255, 255, 255)
MUTED = rgb(128, 158, 174)
GREEN = rgb(80, 210, 154)
AMBER = rgb(250, 179, 68)
RED = rgb(239, 94, 94)

T, F = -1, 0
BLANK = 12


class Deck:
    def __init__(self) -> None:
        self.ppt = win32.gencache.EnsureDispatch("PowerPoint.Application")
        self.ppt.Visible = T
        self.pres = self.ppt.Presentations.Add()
        self.pres.PageSetup.SlideWidth = 960
        self.pres.PageSetup.SlideHeight = 540

    def slide(self):
        s = self.pres.Slides.Add(self.pres.Slides.Count + 1, BLANK)
        s.FollowMasterBackground = False
        s.Background.Fill.Solid()
        s.Background.Fill.ForeColor.RGB = BLACK
        # permanent technical grid / rails
        self.line(s, 30, 78, 930, 78, PANEL2, 0.7)
        self.line(s, 30, 500, 930, 500, PANEL2, 0.7)
        return s

    def rect(self, s, x, y, w, h, fill, line=None, radius=True, anim=False):
        sh = s.Shapes.AddShape(5 if radius else 1, x, y, w, h)
        sh.Fill.Solid()
        sh.Fill.ForeColor.RGB = fill
        if line is None:
            sh.Line.Visible = F
        else:
            sh.Line.ForeColor.RGB = line
            sh.Line.Weight = 1
        if anim:
            sh.AlternativeText = "anim-card"
        return sh

    def circle(self, s, x, y, size, fill, line=None):
        sh = s.Shapes.AddShape(9, x, y, size, size)
        sh.Fill.Solid()
        sh.Fill.ForeColor.RGB = fill
        if line is None:
            sh.Line.Visible = F
        else:
            sh.Line.ForeColor.RGB = line
            sh.Line.Weight = 1
        return sh

    def line(self, s, x1, y1, x2, y2, color, weight=1.5, dash=False):
        sh = s.Shapes.AddLine(x1, y1, x2, y2)
        sh.Line.ForeColor.RGB = color
        sh.Line.Weight = weight
        if dash:
            sh.Line.DashStyle = 4
        return sh

    def text(self, s, x, y, w, h, text, size, bold=False, color=WHITE, align=1, tag="body"):
        sh = s.Shapes.AddTextbox(1, x, y, w, h)
        sh.TextFrame.WordWrap = T
        sh.TextFrame.MarginLeft = 2
        sh.TextFrame.MarginRight = 2
        tr = sh.TextFrame.TextRange
        tr.Text = text
        tr.Font.Name = "Aptos"
        tr.Font.Size = size
        tr.Font.Bold = T if bold else F
        tr.Font.Color.RGB = color
        tr.ParagraphFormat.Alignment = align
        try:
            tr.ParagraphFormat.SpaceWithin = 1.0
        except Exception:
            pass
        sh.AlternativeText = f"anim-{tag}"
        return sh

    def picture(self, s, path: Path, x, y, w, h, anim=True):
        if not path.is_file():
            return None
        sh = s.Shapes.AddPicture(str(path), F, T, x, y, w, h)
        if anim:
            sh.AlternativeText = "anim-picture"
        return sh

    def top(self, s, section: str, title: str, subtitle: str = ""):
        self.text(s, 32, 20, 125, 20, section.upper(), 9, True, CYAN, 1, "title")
        self.text(s, 32, 42, 710, 34, title, 25, True, WHITE, 1, "title")
        if subtitle:
            self.text(s, 560, 48, 330, 22, subtitle, 10, False, MUTED, 3, "subtitle")
        self.rect(s, 902, 24, 28, 28, PANEL, CYAN, radius=True)
        self.text(s, 902, 31, 28, 16, f"{s.SlideIndex:02d}", 9, True, ICE, 2, "title")

    def footer(self, s, label: str):
        self.circle(s, 32, 513, 8, CYAN)
        self.text(s, 47, 508, 700, 18, label, 9, False, MUTED, 1, "footer")
        self.text(s, 810, 508, 120, 18, "AIRPORTER / LIVE", 8, True, CYAN, 3, "footer")

    def card(self, s, x, y, w, h, number, title, body, accent=CYAN):
        self.rect(s, x, y, w, h, PANEL, PANEL2, True, True)
        self.text(s, x + 16, y + 15, 40, 22, number, 10, True, accent, 1, "card")
        self.text(s, x + 16, y + 48, w - 32, 36, title, 16, True, WHITE, 1, "card")
        self.text(s, x + 16, y + 95, w - 32, h - 110, body, 11.5, False, MUTED, 1, "card")

    def add_motion(self) -> None:
        """Add slide transitions and entrance animations to tagged shapes."""
        for idx in range(1, self.pres.Slides.Count + 1):
            s = self.pres.Slides(idx)
            trans = s.SlideShowTransition
            trans.EntryEffect = (
                c.ppEffectFade
                if idx % 3 == 1
                else (c.ppEffectPushLeft if idx % 3 == 2 else c.ppEffectPushRight)
            )
            trans.Duration = 0.65
            trans.AdvanceOnClick = T

            seq = s.TimeLine.MainSequence
            order = 0
            for j in range(1, s.Shapes.Count + 1):
                sh = s.Shapes(j)
                tag = str(getattr(sh, "AlternativeText", "") or "")
                if not tag.startswith("anim-"):
                    continue
                if "footer" in tag:
                    continue
                effect = c.msoAnimEffectFloat if "title" in tag or "picture" in tag else c.msoAnimEffectFade
                trigger = c.msoAnimTriggerWithPrevious if order == 0 else c.msoAnimTriggerAfterPrevious
                try:
                    eff = seq.AddEffect(sh, effect, trigger)
                    eff.Timing.Duration = 0.45 if "title" in tag else 0.32
                    if order > 0:
                        eff.Timing.TriggerDelayTime = 0.05
                    order += 1
                except Exception:
                    pass

    def save(self, path: Path):
        if path.exists():
            path.unlink()
        self.add_motion()
        self.pres.SaveAs(str(path))
        self.pres.Close()
        self.ppt.Quit()


RU = {
    "cover_sub": "Мобильный робот-ассистент для аэропорта",
    "cover_pitch": "Навигация · сопровождение · работа с багажом",
    "cover_note": "Рабочий прототип на Raspberry Pi 5 + Arduino Mega + ROS 2",
    "problem_intro": "Аэропорт объединяет десятки сервисов, длинные маршруты и большой поток информации. Для пассажира это часто означает лишний стресс и потерю времени.",
    "problem": [
        ("01", "Багаж", "Физическая нагрузка: вещи приходится перевозить по длинным переходам терминала."),
        ("02", "Навигация", "Сложно быстро найти регистрацию, нужный сервис или выход на посадку."),
        ("03", "Язык", "Иностранным и редко летающим пассажирам трудно получить понятную информацию."),
    ],
    "concept": "AirPorter объединяет информационный киоск и мобильную платформу. После сканирования билета пассажир видит данные рейса и выбирает подходящий формат помощи.",
    "journey": [
        ("01", "Подойти", "Пассажир начинает работу через сенсорный экран."),
        ("02", "Сканировать", "Система получает основную информацию по билету."),
        ("03", "Выбрать", "Информация, сопровождение или перевозка багажа."),
        ("04", "Получить помощь", "Робот показывает маршрут или начинает движение."),
        ("05", "Завершить", "Пассажир приходит к нужной точке или посадке."),
    ],
    "scenarios": [
        ("01", "Только информация", "Робот показывает рейс, выход, время посадки, сервисы и маршрут. После этого сессия завершается."),
        ("02", "Сопровождение", "Пассажир выбирает точки: регистрация, туалет, Duty Free, кафе или выход. Робот строит маршрут и ведёт человека."),
        ("03", "Только багаж", "Робот берёт вещи и проходит этапы проверки багажа. Пассажиру остаётся пройти личный досмотр и сесть в самолёт."),
    ],
    "hardware_intro": "Реальный прототип собран на деревянной платформе размером 82 × 56 см. Внутри — вычислительный модуль, контроллер движения, приводы и силовая электроника.",
    "hardware": [
        ("COMPUTE", "Raspberry Pi 5, 16 ГБ", "ROS 2 Jazzy, карта, навигация, камера, веб-интерфейсы."),
        ("CONTROL", "Arduino Mega 2560", "Управление моторами, энкодеры, watchdog и безопасный стоп."),
        ("DRIVE", "4× Mecanum", "JGB37-520 + L298N, движение вперёд, назад, боком и разворот."),
        ("SENSE", "COIN D6 + камера", "Лидарная карта, препятствия, билет и сценарии взаимодействия."),
    ],
    "architecture_intro": "Система разделена на уровни. Такое устройство упрощает диагностику, не смешивает высокоуровневую навигацию с безопасным управлением моторами и позволяет постепенно заменять детали на промышленные.",
    "architecture": [
        ("SENSORS", "Лидар · камера · энкодеры"),
        ("ROS 2", "Карта · поза · A* · маршрут"),
        ("MEGA", "Моторы · плавный старт · стоп"),
        ("UI", "Киоск пассажира · админ-панель"),
    ],
    "navigation_intro": "Прототип использует собственный стек ROS 2: occupancy grid, A*, следование по маршруту и корректировку позы по лидару и энкодерам. Это не готовый Nav2-шаблон, а отдельная реализация команды.",
    "navigation": [
        ("Карта", "Лидар строит и обновляет карту помещения."),
        ("Положение", "Оценка позы учитывает одометрию и совпадение сканов."),
        ("Маршрут", "A* ищет путь, учитывая габариты робота 82 × 56 см."),
        ("Контроль", "Есть waypoints, телеуправление и операторская панель."),
    ],
    "interface_intro": "Пассажирский киоск работает на сенсорном экране. Основные действия вынесены крупно, а интерфейс поддерживает несколько языков и билетные сценарии.",
    "interface": [
        ("PASSENGER", "Киоск", "Выбор сервиса, скан билета, маршрут и статус сопровождения."),
        ("LANGUAGES", "RU · EN · TT", "Русский, английский и татарский интерфейс."),
        ("OPERATOR", "Админ-панель", "Health, карта, STOP, миссия, логи и полный режим управления."),
    ],
    "safety_intro": "Рядом с пассажирами важнее предсказуемость, чем максимальная скорость. Поэтому система строится вокруг остановки, контроля связи и ручного вмешательства.",
    "safety": [
        ("STOP", "Остановка при потере команды или соединения."),
        ("WATCHDOG", "Arduino и drive-слой ограничивают время действия команды."),
        ("OBSTACLES", "Лидар помогает видеть препятствия и корректировать путь."),
        ("OPERATOR", "Оператор может остановить миссию и взять управление."),
        ("FOOTPRINT", "Навигация учитывает физический размер корпуса."),
        ("STATUS", "Health-панель показывает состояние процессов и устройств."),
    ],
    "prototype_intro": "На текущем этапе это инженерный прототип, а не сертифицированный аэропортовый продукт. Уже реализованы ключевые программные и аппаратные функции для демонстрации концепции.",
    "prototype": [
        "Интерактивный киоск и многоязычный интерфейс",
        "Лидарная карта и отображение положения",
        "Телеуправление и проезд по точкам",
        "Демо-сценарии escort и работы с билетом",
        "Админ-панель и дистанционная диагностика",
        "Перевозка груза на платформе",
    ],
    "economics": "Текущий прототип стоит около 90 000 рублей. Модульная архитектура позволяет модернизировать контроллеры, приводы, сенсоры и корпус по отдельности — без полной замены системы.",
    "expert": "Проект получил положительную обратную связь от представителей авиационной отрасли и вызвал интерес к дальнейшему тестированию. Реальная эксплуатация в терминале остаётся следующим этапом, а не заявленным результатом.",
    "roadmap": [
        ("01", "Механика", "Металлический каркас и промышленные Mecanum-колёса."),
        ("02", "Электроника", "Переход на промышленные драйверы, питание и сенсоры."),
        ("03", "Навигация", "Дополнительные камеры, 360° обзор и более устойчивое позиционирование."),
        ("04", "Сервис", "Приложение пассажира, fleet-панель и хаб зарядки/ремонта."),
        ("05", "Испытания", "Проверка сценариев в условиях реального аэропорта."),
    ],
    "closing": "AirPorter превращает сложный маршрут по терминалу в понятный сервис: показать, сопроводить и помочь с багажом.",
}

EN = {
    "cover_sub": "A mobile robot assistant for airports",
    "cover_pitch": "Navigation · escort · luggage assistance",
    "cover_note": "Working prototype: Raspberry Pi 5 + Arduino Mega + ROS 2",
    "problem_intro": "An airport combines dozens of services, long routes, and a large information flow. For passengers, this often means extra stress and lost time.",
    "problem": [
        ("01", "Luggage", "Physical strain: bags must be moved across long terminal routes."),
        ("02", "Navigation", "Finding check-in, a service point, or the gate quickly is difficult."),
        ("03", "Language", "International and infrequent travelers may struggle to get clear information."),
    ],
    "concept": "AirPorter combines an information kiosk with a mobile platform. After scanning a ticket, the passenger sees flight data and chooses the right type of assistance.",
    "journey": [
        ("01", "Approach", "The passenger starts through the touchscreen."),
        ("02", "Scan", "The system reads key ticket information."),
        ("03", "Choose", "Information, escort, or luggage transport."),
        ("04", "Get assistance", "The robot shows the route or starts moving."),
        ("05", "Complete", "The passenger reaches the destination or boarding."),
    ],
    "scenarios": [
        ("01", "Information only", "The robot shows flight, gate, boarding time, services, and route. The session then ends."),
        ("02", "Escort", "The passenger selects check-in, restroom, Duty Free, café, or gate. The robot plans a route and guides the person."),
        ("03", "Luggage only", "The robot takes the bags through baggage screening. The passenger completes personal security and boards."),
    ],
    "hardware_intro": "The real prototype is assembled on an 82 × 56 cm wooden platform. It contains the compute module, motion controller, drives, and power electronics.",
    "hardware": [
        ("COMPUTE", "Raspberry Pi 5, 16 GB", "ROS 2 Jazzy, mapping, navigation, camera, and web interfaces."),
        ("CONTROL", "Arduino Mega 2560", "Motor control, encoders, watchdog, and safe stop."),
        ("DRIVE", "4× Mecanum", "JGB37-520 + L298N; forward, reverse, strafing, and rotation."),
        ("SENSE", "COIN D6 + camera", "Lidar map, obstacles, ticket, and interaction scenarios."),
    ],
    "architecture_intro": "The system is split into layers. This simplifies diagnostics, separates high-level navigation from safe motor control, and supports gradual replacement with industrial parts.",
    "architecture": [
        ("SENSORS", "Lidar · camera · encoders"),
        ("ROS 2", "Map · pose · A* · route"),
        ("MEGA", "Motors · smooth start · stop"),
        ("UI", "Passenger kiosk · admin panel"),
    ],
    "navigation_intro": "The prototype uses a custom ROS 2 stack: occupancy grid, A*, route following, and pose correction from lidar and encoders. It is a team-built implementation rather than a preconfigured Nav2 template.",
    "navigation": [
        ("Map", "Lidar builds and updates the indoor map."),
        ("Pose", "Pose estimation combines odometry and scan matching."),
        ("Route", "A* plans around the robot’s 82 × 56 cm footprint."),
        ("Control", "Waypoints, teleoperation, and operator panel are available."),
    ],
    "interface_intro": "The passenger kiosk runs on a touchscreen. Main actions are large and clear; the UI supports multiple languages and ticket scenarios.",
    "interface": [
        ("PASSENGER", "Kiosk", "Service selection, ticket scan, route, and escort status."),
        ("LANGUAGES", "RU · EN · TT", "Russian, English, and Tatar interface."),
        ("OPERATOR", "Admin panel", "Health, map, STOP, mission, logs, and full control mode."),
    ],
    "safety_intro": "Near passengers, predictable behavior matters more than maximum speed. The system is therefore built around stopping, connection monitoring, and manual intervention.",
    "safety": [
        ("STOP", "Stop when commands or connection are lost."),
        ("WATCHDOG", "Arduino and drive layer limit command lifetime."),
        ("OBSTACLES", "Lidar supports obstacle detection and route correction."),
        ("OPERATOR", "An operator can stop the mission and take control."),
        ("FOOTPRINT", "Navigation accounts for the physical body size."),
        ("STATUS", "Health panel shows process and device state."),
    ],
    "prototype_intro": "At this stage, it is an engineering prototype — not a certified airport product. Core hardware and software functions already demonstrate the concept.",
    "prototype": [
        "Interactive kiosk and multilingual interface",
        "Lidar mapping and pose visualization",
        "Teleoperation and waypoint travel",
        "Demo escort and ticket flows",
        "Admin panel and remote diagnostics",
        "Payload transport on the platform",
    ],
    "economics": "The current prototype costs about 90,000 RUB. Modular architecture allows controllers, drives, sensors, and body structure to be upgraded independently.",
    "expert": "The project received positive aviation-industry feedback and interest in further testing. Real terminal operation remains the next stage, not a claimed current result.",
    "roadmap": [
        ("01", "Mechanics", "Metal frame and industrial Mecanum wheels."),
        ("02", "Electronics", "Industrial drivers, power, and sensors."),
        ("03", "Navigation", "Additional cameras, 360° view, and stronger localization."),
        ("04", "Service", "Passenger app, fleet panel, charging and repair hub."),
        ("05", "Trials", "Validate scenarios in a real airport environment."),
    ],
    "closing": "AirPorter turns a complex terminal journey into a clear service: inform, guide, and help with luggage.",
}


def build(lang: str, data: dict, path: Path) -> None:
    d = Deck()
    ru = lang == "ru"

    # 1 — Cover, built from actual project materials.
    s = d.slide()
    d.rect(s, 0, 0, 960, 540, BLACK, None, False)
    d.rect(s, 0, 0, 14, 540, CYAN, None, False)
    d.picture(s, LOGO, 45, 55, 300, 300)
    d.rect(s, 500, 52, 410, 312, PANEL, CYAN, True, True)
    d.picture(s, ROBOT, 512, 64, 386, 220)
    d.text(s, 525, 300, 350, 25, "REAL PROTOTYPE / 82 × 56 CM", 10, True, CYAN, 1, "title")
    d.text(s, 52, 362, 420, 38, data["cover_sub"], 22, True, WHITE, 1, "title")
    d.text(s, 52, 412, 430, 28, data["cover_pitch"], 13, False, ICE, 1, "subtitle")
    d.text(s, 515, 390, 390, 60, data["cover_note"], 12, False, MUTED, 1, "body")
    d.footer(s, "PROJECT DEFENSE / 2026")

    # 2 — Problem
    s = d.slide()
    d.top(s, "02 / PROBLEM", "Проблема" if ru else "The problem")
    d.text(s, 32, 100, 896, 55, data["problem_intro"], 14, False, ICE, 1, "body")
    x = 32
    for n, title, body in data["problem"]:
        d.card(s, x, 190, 286, 250, n, title, body, AMBER if n == "01" else CYAN)
        x += 306
    d.footer(s, "WHY THE PROJECT MATTERS")

    # 3 — Concept
    s = d.slide()
    d.top(s, "03 / CONCEPT", "Концепция решения" if ru else "Solution concept")
    d.text(s, 32, 105, 896, 68, data["concept"], 15, False, ICE, 1, "body")
    modules = [
        ("SCAN", "Ticket" if not ru else "Билет", "flight + passenger"),
        ("SELECT", "Scenario" if not ru else "Сценарий", "info / escort / luggage"),
        ("ACT", "Assist" if not ru else "Помощь", "route + movement"),
    ]
    x = 65
    for i, (code, title, sub) in enumerate(modules):
        d.circle(s, x + 78, 215, 80, CYAN if i < 2 else GREEN, PANEL2)
        d.text(s, x + 78, 240, 80, 22, f"{i+1:02d}", 16, True, BLACK, 2, "card")
        d.text(s, x, 310, 236, 35, title, 18, True, WHITE, 2, "card")
        d.text(s, x, 352, 236, 30, f"{code} / {sub}", 11, False, MUTED, 2, "card")
        if i < 2:
            d.line(s, x + 185, 255, x + 285, 255, CYAN, 2, True)
        x += 306
    d.footer(s, "SCAN → SELECT → ASSIST")

    # 4 — Passenger journey
    s = d.slide()
    d.top(s, "04 / JOURNEY", "Путь пассажира" if ru else "Passenger journey")
    d.line(s, 90, 260, 870, 260, CYAN, 2, True)
    x = 50
    for n, title, body in data["journey"]:
        d.circle(s, x + 55, 225, 70, PANEL2, CYAN)
        d.text(s, x + 55, 248, 70, 20, n, 12, True, CYAN, 2, "card")
        d.text(s, x, 315, 180, 30, title, 13, True, WHITE, 2, "card")
        d.text(s, x, 352, 180, 75, body, 10.5, False, MUTED, 2, "card")
        x += 180
    d.footer(s, "FROM TOUCHSCREEN TO DESTINATION")

    # 5 — Scenarios
    s = d.slide()
    d.top(s, "05 / MODES", "Три сценария работы" if ru else "Three operating scenarios")
    x = 32
    accents = [CYAN, GREEN, AMBER]
    for i, (n, title, body) in enumerate(data["scenarios"]):
        d.rect(s, x, 115, 286, 330, PANEL, accents[i], True, True)
        d.text(s, x + 18, 138, 55, 24, n, 12, True, accents[i], 1, "card")
        d.text(s, x + 18, 185, 250, 60, title, 18, True, WHITE, 1, "card")
        d.text(s, x + 18, 265, 250, 135, body, 12, False, MUTED, 1, "card")
        x += 306
    d.footer(s, "INFO / ESCORT / LUGGAGE")

    # 6 — Hardware + actual photograph
    s = d.slide()
    d.top(s, "06 / HARDWARE", "Аппаратная платформа" if ru else "Hardware platform")
    d.picture(s, ROBOT, 32, 105, 500, 285)
    d.rect(s, 32, 105, 500, 285, BLACK, CYAN, True, False).Fill.Transparency = 1.0
    d.text(s, 48, 405, 485, 65, data["hardware_intro"], 11.5, False, MUTED, 1, "body")
    y = 105
    for code, title, body in data["hardware"]:
        d.rect(s, 560, y, 368, 80, PANEL, PANEL2, True, True)
        d.text(s, 575, y + 12, 78, 18, code, 8, True, CYAN, 1, "card")
        d.text(s, 655, y + 10, 255, 24, title, 13, True, WHITE, 1, "card")
        d.text(s, 575, y + 40, 335, 32, body, 9.5, False, MUTED, 1, "card")
        y += 92
    d.footer(s, "REAL PROTOTYPE / MATERIALS")

    # 7 — Architecture
    s = d.slide()
    d.top(s, "07 / SYSTEM", "Архитектура" if ru else "System architecture")
    d.text(s, 32, 100, 896, 62, data["architecture_intro"], 12.5, False, ICE, 1, "body")
    x = 32
    for i, (title, body) in enumerate(data["architecture"]):
        d.rect(s, x, 210, 205, 190, PANEL, CYAN if i != 2 else GREEN, True, True)
        d.text(s, x + 15, 230, 175, 32, title, 15, True, WHITE, 1, "card")
        d.text(s, x + 15, 285, 175, 65, body, 11, False, MUTED, 1, "card")
        if i < 3:
            d.text(s, x + 205, 280, 35, 35, "→", 22, True, CYAN, 2, "card")
        x += 230
    d.footer(s, "SENSE → THINK → MOVE → INTERACT")

    # 8 — Navigation
    s = d.slide()
    d.top(s, "08 / NAV", "Навигация" if ru else "Navigation")
    d.text(s, 32, 100, 896, 75, data["navigation_intro"], 12.5, False, ICE, 1, "body")
    x = 32
    for i, (title, body) in enumerate(data["navigation"]):
        d.rect(s, x, 210, 210, 225, PANEL, PANEL2, True, True)
        d.circle(s, x + 15, 228, 18, CYAN if i != 2 else GREEN)
        d.text(s, x + 45, 220, 145, 35, title, 14, True, WHITE, 1, "card")
        d.text(s, x + 15, 280, 180, 100, body, 11, False, MUTED, 1, "card")
        x += 228
    d.footer(s, "CUSTOM ROS 2 STACK / A* / OCCUPANCY GRID")

    # 9 — Interface
    s = d.slide()
    d.top(s, "09 / UX", "Интерфейсы" if ru else "Interfaces")
    d.text(s, 32, 100, 896, 60, data["interface_intro"], 13, False, ICE, 1, "body")
    x = 32
    for i, (code, title, body) in enumerate(data["interface"]):
        accent = [CYAN, GREEN, AMBER][i]
        d.rect(s, x, 200, 286, 235, PANEL, accent, True, True)
        d.text(s, x + 16, 218, 250, 20, code, 9, True, accent, 1, "card")
        d.text(s, x + 16, 260, 250, 35, title, 17, True, WHITE, 1, "card")
        d.text(s, x + 16, 315, 250, 85, body, 11, False, MUTED, 1, "card")
        x += 306
    d.footer(s, "PASSENGER + OPERATOR")

    # 10 — Safety
    s = d.slide()
    d.top(s, "10 / SAFETY", "Безопасность" if ru else "Safety")
    d.text(s, 32, 100, 896, 60, data["safety_intro"], 13, False, ICE, 1, "body")
    for i, (code, body) in enumerate(data["safety"]):
        col, row = i % 3, i // 3
        x, y = 32 + col * 306, 190 + row * 125
        d.rect(s, x, y, 286, 105, PANEL, PANEL2, True, True)
        d.text(s, x + 15, y + 14, 100, 20, code, 9, True, GREEN if i < 2 else CYAN, 1, "card")
        d.text(s, x + 15, y + 44, 250, 45, body, 10.5, False, MUTED, 1, "card")
    d.footer(s, "STOP FIRST / PREDICTABLE MOTION")

    # 11 — Prototype truth
    s = d.slide()
    d.top(s, "11 / STATUS", "Первый прототип" if ru else "Current prototype")
    d.text(s, 32, 100, 896, 65, data["prototype_intro"], 13, False, ICE, 1, "body")
    for i, item in enumerate(data["prototype"]):
        col, row = i % 2, i // 2
        x, y = 32 + col * 458, 190 + row * 85
        d.rect(s, x, y, 438, 66, PANEL, PANEL2, True, True)
        d.text(s, x + 14, y + 20, 32, 22, "✓", 14, True, GREEN, 2, "card")
        d.text(s, x + 55, y + 18, 365, 30, item, 11.5, False, WHITE, 1, "card")
    d.footer(s, "WORKING DEMO ≠ CERTIFIED DEPLOYMENT")

    # 12 — Validation / economics
    s = d.slide()
    d.top(s, "12 / VALUE", "Оценка и экономика" if ru else "Validation and economics")
    d.rect(s, 32, 110, 438, 330, PANEL, CYAN, True, True)
    d.text(s, 55, 140, 390, 35, "90 000 ₽" if ru else "90,000 RUB", 32, True, CYAN, 1, "title")
    d.text(s, 55, 195, 390, 28, "Текущий прототип" if ru else "Current prototype", 13, True, WHITE, 1, "card")
    d.text(s, 55, 250, 390, 150, data["economics"], 12, False, MUTED, 1, "body")
    d.rect(s, 490, 110, 438, 330, PANEL, GREEN, True, True)
    d.text(s, 515, 140, 390, 35, "EXPERT FEEDBACK", 16, True, GREEN, 1, "title")
    d.text(s, 515, 205, 390, 190, data["expert"], 12, False, MUTED, 1, "body")
    d.footer(s, "MODULAR / TESTABLE / HONEST")

    # 13 — Roadmap
    s = d.slide()
    d.top(s, "13 / ROADMAP", "Планы развития" if ru else "Development roadmap")
    d.line(s, 120, 270, 840, 270, CYAN, 2, True)
    x = 55
    for i, (n, title, body) in enumerate(data["roadmap"]):
        d.circle(s, x + 55, 235, 70, PANEL2, CYAN if i < 4 else GREEN)
        d.text(s, x + 55, 258, 70, 20, n, 12, True, CYAN if i < 4 else GREEN, 2, "card")
        d.text(s, x, 330, 180, 28, title, 13, True, WHITE, 2, "card")
        d.text(s, x, 367, 180, 70, body, 10, False, MUTED, 2, "card")
        x += 180
    d.footer(s, "MECHANICS → ELECTRONICS → NAV → SERVICE → TRIALS")

    # 14 — Closing
    s = d.slide()
    d.rect(s, 0, 0, 960, 540, BLACK, None, False)
    d.picture(s, LOGO, 330, 35, 300, 300)
    d.text(s, 100, 345, 760, 55, data["closing"], 19, True, WHITE, 2, "title")
    d.text(s, 100, 420, 760, 30, "СПАСИБО!" if ru else "THANK YOU!", 14, True, CYAN, 2, "subtitle")
    d.footer(s, "QUESTIONS / AIRPORTER TEAM")

    d.save(path)
    print("saved", path)


if __name__ == "__main__":
    build("ru", RU, DESKTOP / "AirPorter Animated RU v5.pptx")
    build("en", EN, DESKTOP / "AirPorter Animated EN v5.pptx")
    print("DONE")
