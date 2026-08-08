# -*- coding: utf-8 -*-
"""Build AirPorter presentation decks (RU + EN) via PowerPoint COM."""
from __future__ import annotations

import os
from pathlib import Path

import win32com.client as win32

DESKTOP = Path(os.path.expanduser(r"~\Desktop"))
LOGO = Path(r"C:\Users\user\Projects\lidar\monitor\assets\kazan-airport-logo-white.png")
PLANE = Path(r"C:\Users\user\Projects\lidar\monitor\assets\realistic-airliner-balanced.png")

# RGB packed for PowerPoint COM
def rgb(r: int, g: int, b: int) -> int:
    return r + (g << 8) + (b << 16)


NAVY = rgb(11, 31, 51)
NAVY2 = rgb(18, 48, 74)
TEAL = rgb(32, 140, 166)
SKY = rgb(90, 178, 210)
CREAM = rgb(245, 241, 234)
INK = rgb(18, 28, 38)
MUTED = rgb(90, 110, 128)
WHITE = rgb(255, 255, 255)
ACCENT = rgb(212, 160, 74)
LINE = rgb(210, 220, 230)

PP_LAYOUT_BLANK = 12
MSO_SHAPE_RECT = 1
MSO_TRUE = -1
MSO_FALSE = 0


class Deck:
    def __init__(self) -> None:
        self.ppt = win32.Dispatch("PowerPoint.Application")
        self.ppt.Visible = MSO_TRUE
        self.pres = self.ppt.Presentations.Add()
        self.pres.PageSetup.SlideWidth = 960
        self.pres.PageSetup.SlideHeight = 540

    def blank(self):
        return self.pres.Slides.Add(self.pres.Slides.Count + 1, PP_LAYOUT_BLANK)

    def bg(self, slide, color: int) -> None:
        slide.FollowMasterBackground = False
        slide.Background.Fill.Solid()
        slide.Background.Fill.ForeColor.RGB = color

    def rect(self, slide, l, t, w, h, fill, line=None):
        s = slide.Shapes.AddShape(MSO_SHAPE_RECT, l, t, w, h)
        s.Fill.Solid()
        s.Fill.ForeColor.RGB = fill
        if line is None:
            s.Line.Visible = MSO_FALSE
        else:
            s.Line.ForeColor.RGB = line
            s.Line.Weight = 1
        return s

    def text(self, slide, l, t, w, h, txt, size, bold, color, align=1):
        tb = slide.Shapes.AddTextbox(1, l, t, w, h)
        tr = tb.TextFrame.TextRange
        tr.Text = txt
        tr.Font.Name = "Calibri"
        tr.Font.Size = size
        tr.Font.Bold = MSO_TRUE if bold else MSO_FALSE
        tr.Font.Color.RGB = color
        tr.ParagraphFormat.Alignment = align
        tb.TextFrame.WordWrap = MSO_TRUE
        return tb

    def pic(self, slide, path: Path, l, t, w, h) -> None:
        if path.is_file():
            try:
                slide.Shapes.AddPicture(str(path), MSO_FALSE, MSO_TRUE, l, t, w, h)
            except Exception:
                pass

    def footer(self, slide, label: str, dark: bool = True) -> None:
        c = SKY if dark else MUTED
        self.text(slide, 30, 510, 700, 24, label, 11, False, c, 1)
        self.text(slide, 780, 510, 160, 24, "AirPorter", 11, True, c, 3)

    def save(self, path: Path) -> None:
        if path.exists():
            path.unlink()
        self.pres.SaveAs(str(path))
        self.pres.Close()
        self.ppt.Quit()


def build_ru(path: Path) -> None:
    d = Deck()

    # Title
    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 18, 540, TEAL)
    d.rect(s, 0, 500, 960, 40, NAVY2)
    d.pic(s, LOGO, 40, 36, 160, 42)
    d.pic(s, PLANE, 560, 120, 360, 200)
    d.text(s, 40, 140, 500, 70, "AirPorter", 48, True, WHITE, 1)
    d.text(s, 40, 210, 520, 90, "Мобильный робот-ассистент\nдля аэропорта", 26, False, SKY, 1)
    d.text(s, 40, 340, 480, 40, "Проект команды AirPorter", 16, False, CREAM, 1)

    # Problem
    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 700, 40, "Проблема", 28, True, WHITE, 1)
    d.text(
        s,
        36,
        100,
        880,
        70,
        "Современный аэропорт — сложная система. Для многих пассажиров ориентирование становится серьёзной проблемой.",
        18,
        False,
        INK,
        1,
    )
    cards = [
        ("Багаж", "Физическая нагрузка при перевозке вещей"),
        ("Навигация", "Сложная схема терминала и сервисов"),
        ("Язык", "Барьер при получении информации"),
    ]
    x = 36
    for title, desc in cards:
        d.rect(s, x, 200, 280, 200, WHITE, LINE)
        d.rect(s, x, 200, 280, 8, TEAL)
        d.text(s, x + 18, 230, 244, 40, title, 22, True, NAVY, 1)
        d.text(s, x + 18, 290, 244, 80, desc, 16, False, MUTED, 1)
        x += 300
    d.footer(s, "Слайд 2 · Проблема", False)

    # Solution pipeline
    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Решение — AirPorter", 28, True, WHITE, 1)
    d.text(
        s,
        36,
        100,
        880,
        50,
        "Робот-ассистент помогает пассажиру пройти путь от старта до цели с учётом его потребностей.",
        18,
        False,
        INK,
        1,
    )
    steps = [
        ("01", "Скан билета", "Рейс, пассажир, базовые данные"),
        ("02", "Информация", "Выход, время, сервисы на экране"),
        ("03", "Сценарий", "Инфо · escort · только багаж"),
    ]
    x = 36
    for n, t, desc in steps:
        d.rect(s, x, 200, 280, 220, NAVY)
        d.text(s, x + 20, 220, 240, 36, n, 28, True, ACCENT, 1)
        d.text(s, x + 20, 270, 240, 40, t, 20, True, WHITE, 1)
        d.text(s, x + 20, 320, 240, 70, desc, 15, False, SKY, 1)
        x += 300
    d.footer(s, "Слайд 3 · Решение", False)

    # Scenarios
    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Три сценария работы", 28, True, WHITE, 1)
    scenarios = [
        ("1", "Только информация", "Маршрут и данные на экране. Сессия завершается."),
        ("2", "Сопровождение", "Маршрут через регистрацию, сервисы или выход. Робот ведёт пассажира."),
        (
            "3",
            "Только багаж",
            "Робот проходит проверку багажа. Пассажиру — личный досмотр и посадка.",
        ),
    ]
    y = 100
    for n, t, desc in scenarios:
        d.rect(s, 36, y, 60, 70, TEAL)
        d.text(s, 48, y + 16, 40, 40, n, 24, True, WHITE, 2)
        d.rect(s, 110, y, 814, 70, WHITE, LINE)
        d.text(s, 130, y + 8, 780, 28, t, 18, True, NAVY, 1)
        d.text(s, 130, y + 36, 780, 28, desc, 14, False, MUTED, 1)
        y += 90
    d.footer(s, "Слайд 3 · Сценарии", False)

    # Hardware
    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Аппаратная платформа", 28, True, WHITE, 1)
    d.text(s, 36, 95, 880, 30, "Первый рабочий прототип", 16, False, MUTED, 1)
    hw = [
        ("Raspberry Pi 5", "16 ГБ · ROS 2 Jazzy · лидар · камера · логика"),
        ("Arduino Mega 2560", "Энкодеры · точное управление моторами"),
        ("Mecanum + COIN D6", "Омни-движение · лидар · экран 10,1\""),
        ("Привод", "L298N · моторы JGB37-520"),
    ]
    coords = [(36, 150), (490, 150), (36, 320), (490, 320)]
    for (cx, cy), (t, desc) in zip(coords, hw):
        d.rect(s, cx, cy, 430, 140, WHITE, LINE)
        d.rect(s, cx, cy, 8, 140, TEAL)
        d.text(s, cx + 24, cy + 24, 380, 36, t, 20, True, NAVY, 1)
        d.text(s, cx + 24, cy + 70, 380, 50, desc, 15, False, MUTED, 1)
    d.footer(s, "Слайд 4 · Железо", False)

    # Navigation
    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 18, 540, TEAL)
    d.text(s, 50, 60, 860, 50, "Навигация", 32, True, WHITE, 1)
    for y, line in [
        (150, "Карта помещения по лидару"),
        (210, "Оценка позы · габариты корпуса · энкодеры"),
        (270, "Маршрут и объезд препятствий"),
        (330, "Проезд по точкам и операторский контроль"),
    ]:
        d.rect(s, 50, y, 18, 18, ACCENT)
        d.text(s, 86, y - 6, 800, 36, line, 20, False, CREAM, 1)
    d.footer(s, "Слайд 5 · Навигация", True)

    # UI
    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Интерфейс пассажира", 28, True, WHITE, 1)
    d.text(
        s,
        36,
        100,
        880,
        50,
        "Киоск на сенсорном экране: регистрация, посадка, багаж, информация и другие точки терминала.",
        17,
        False,
        INK,
        1,
    )
    x = 36
    for lang in ("Русский", "English", "Татарча"):
        d.rect(s, x, 200, 280, 100, NAVY)
        d.text(s, x, 230, 280, 40, lang, 22, True, WHITE, 2)
        x += 300
    d.text(
        s,
        36,
        340,
        880,
        50,
        "Простой интерфейс в тематике аэропорта — понятен без инструкций.",
        16,
        False,
        MUTED,
        1,
    )
    d.footer(s, "Слайд 6 · Интерфейс", False)

    # Safety
    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Безопасность", 28, True, WHITE, 1)
    safe = [
        "Стоп при потере связи",
        "Контроль маршрута",
        "Распознавание препятствий",
        "Корпус из оргстекла",
        "Небольшой клиренс",
        "Световая индикация",
    ]
    for i, item in enumerate(safe):
        col, row = i % 3, i // 3
        x, y = 36 + col * 300, 120 + row * 150
        d.rect(s, x, y, 280, 120, WHITE, LINE)
        d.rect(s, x, y, 280, 6, ACCENT)
        d.text(s, x + 20, y + 40, 240, 50, item, 16, True, NAVY, 1)
    d.footer(s, "Слайд 7 · Безопасность", False)

    # Prototype
    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 18, 540, ACCENT)
    d.text(s, 50, 80, 860, 50, "Первый прототип", 32, True, WHITE, 1)
    d.text(
        s,
        50,
        160,
        860,
        120,
        "Интерактивное меню · проезд по точкам ·\nориентирование в пространстве · перевозка груза",
        24,
        False,
        SKY,
        1,
    )
    d.text(
        s,
        50,
        360,
        860,
        40,
        "Работающая платформа, готовая к демонстрации и доработке.",
        16,
        False,
        CREAM,
        1,
    )
    d.footer(s, "Слайд 8 · Прототип", True)

    # Experts + economics
    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Оценка и экономика", 28, True, WHITE, 1)
    d.rect(s, 36, 120, 430, 300, NAVY)
    d.text(s, 56, 150, 390, 40, "Эксперты", 20, True, ACCENT, 1)
    d.text(
        s,
        56,
        210,
        390,
        160,
        "Положительная оценка авиационной отрасли.\nИнтерес аэропорта к дальнейшим испытаниям.",
        16,
        False,
        CREAM,
        1,
    )
    d.rect(s, 490, 120, 430, 300, WHITE, LINE)
    d.text(s, 510, 150, 390, 40, "Стоимость прототипа", 20, True, NAVY, 1)
    d.text(s, 510, 220, 390, 60, "~ 90 000 ₽", 36, True, TEAL, 1)
    d.text(
        s,
        510,
        300,
        390,
        80,
        "Модульная конструкция — модернизация без полной замены.",
        15,
        False,
        MUTED,
        1,
    )
    d.footer(s, "Слайды 9–10", False)

    # Future
    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Планы на будущее", 28, True, WHITE, 1)
    plans = [
        "Металлический каркас и промышленные Mecanum",
        "Промышленная электроника и сенсорика (в т.ч. 360°)",
        "Приложение для пассажира и панель флота",
        "Хаб зарядки и обслуживания",
        "Испытания в реальных сценариях аэропорта",
    ]
    y = 110
    for i, p in enumerate(plans, 1):
        d.text(s, 50, y, 60, 36, f"{i:02d}", 18, True, TEAL, 1)
        d.text(s, 110, y, 800, 36, p, 17, False, INK, 1)
        y += 55
    d.footer(s, "Слайд 11 · Планы", False)

    # Closing
    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 18, 540, TEAL)
    d.pic(s, LOGO, 380, 80, 200, 52)
    d.text(s, 80, 200, 800, 60, "Спасибо за внимание!", 36, True, WHITE, 2)
    d.text(s, 80, 280, 800, 40, "Команда AirPorter", 22, False, SKY, 2)
    d.text(s, 80, 400, 800, 30, "Вопросы приветствуются", 14, False, MUTED, 2)

    d.save(path)
    print("saved", path)


def build_en(path: Path) -> None:
    d = Deck()

    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 18, 540, TEAL)
    d.pic(s, LOGO, 40, 36, 160, 42)
    d.pic(s, PLANE, 560, 120, 360, 200)
    d.text(s, 40, 140, 500, 70, "AirPorter", 48, True, WHITE, 1)
    d.text(s, 40, 210, 520, 90, "A mobile robot assistant\nfor the airport", 26, False, SKY, 1)
    d.text(s, 40, 340, 480, 40, "Presented by the AirPorter team", 16, False, CREAM, 1)

    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 700, 40, "The problem", 28, True, WHITE, 1)
    d.text(
        s,
        36,
        100,
        880,
        70,
        "Airports are complex. For many passengers, finding the way is a serious challenge.",
        18,
        False,
        INK,
        1,
    )
    cards = [
        ("Luggage", "Physical strain when carrying bags"),
        ("Navigation", "Complex terminal layout and services"),
        ("Language", "Barrier when getting information"),
    ]
    x = 36
    for title, desc in cards:
        d.rect(s, x, 200, 280, 200, WHITE, LINE)
        d.rect(s, x, 200, 280, 8, TEAL)
        d.text(s, x + 18, 230, 244, 40, title, 22, True, NAVY, 1)
        d.text(s, x + 18, 290, 244, 80, desc, 16, False, MUTED, 1)
        x += 300
    d.footer(s, "Slide 2 · Problem", False)

    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "The solution — AirPorter", 28, True, WHITE, 1)
    d.text(
        s,
        36,
        100,
        880,
        50,
        "A robot assistant that helps passengers travel from start to destination.",
        18,
        False,
        INK,
        1,
    )
    steps = [
        ("01", "Scan ticket", "Flight and passenger data"),
        ("02", "Show info", "Gate, time, services on screen"),
        ("03", "Scenario", "Info · escort · luggage-only"),
    ]
    x = 36
    for n, t, desc in steps:
        d.rect(s, x, 200, 280, 220, NAVY)
        d.text(s, x + 20, 220, 240, 36, n, 28, True, ACCENT, 1)
        d.text(s, x + 20, 270, 240, 40, t, 20, True, WHITE, 1)
        d.text(s, x + 20, 320, 240, 70, desc, 15, False, SKY, 1)
        x += 300
    d.footer(s, "Slide 3 · Solution", False)

    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Three scenarios", 28, True, WHITE, 1)
    scenarios = [
        ("1", "Information only", "Route and data on screen. Session ends."),
        ("2", "Escort", "Route via check-in, services, or gate. Robot guides the passenger."),
        ("3", "Luggage only", "Robot handles baggage screening. Passenger does security and boards."),
    ]
    y = 100
    for n, t, desc in scenarios:
        d.rect(s, 36, y, 60, 70, TEAL)
        d.text(s, 48, y + 16, 40, 40, n, 24, True, WHITE, 2)
        d.rect(s, 110, y, 814, 70, WHITE, LINE)
        d.text(s, 130, y + 8, 780, 28, t, 18, True, NAVY, 1)
        d.text(s, 130, y + 36, 780, 28, desc, 14, False, MUTED, 1)
        y += 90
    d.footer(s, "Slide 3 · Scenarios", False)

    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Hardware platform", 28, True, WHITE, 1)
    hw = [
        ("Raspberry Pi 5", "16 GB · ROS 2 Jazzy · lidar · camera · logic"),
        ("Arduino Mega 2560", "Encoders · precise motor control"),
        ("Mecanum + COIN D6", "Omni drive · lidar · 10.1\" screen"),
        ("Drive", "L298N · JGB37-520 motors"),
    ]
    coords = [(36, 150), (490, 150), (36, 320), (490, 320)]
    for (cx, cy), (t, desc) in zip(coords, hw):
        d.rect(s, cx, cy, 430, 140, WHITE, LINE)
        d.rect(s, cx, cy, 8, 140, TEAL)
        d.text(s, cx + 24, cy + 24, 380, 36, t, 20, True, NAVY, 1)
        d.text(s, cx + 24, cy + 70, 380, 50, desc, 15, False, MUTED, 1)
    d.footer(s, "Slide 4 · Hardware", False)

    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 18, 540, TEAL)
    d.text(s, 50, 60, 860, 50, "Navigation", 32, True, WHITE, 1)
    for y, line in [
        (150, "Lidar indoor mapping"),
        (210, "Pose · footprint · encoders"),
        (270, "Routing and obstacle avoidance"),
        (330, "Waypoints and operator control"),
    ]:
        d.rect(s, 50, y, 18, 18, ACCENT)
        d.text(s, 86, y - 6, 800, 36, line, 20, False, CREAM, 1)
    d.footer(s, "Slide 5 · Navigation", True)

    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Passenger interface", 28, True, WHITE, 1)
    d.text(
        s,
        36,
        100,
        880,
        50,
        "Touchscreen kiosk: check-in, boarding, baggage, information, and more.",
        17,
        False,
        INK,
        1,
    )
    x = 36
    for lang in ("Russian", "English", "Tatar"):
        d.rect(s, x, 200, 280, 100, NAVY)
        d.text(s, x, 230, 280, 40, lang, 22, True, WHITE, 2)
        x += 300
    d.footer(s, "Slide 6 · Interface", False)

    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Safety", 28, True, WHITE, 1)
    safe = [
        "Stop on link loss",
        "Route monitoring",
        "Obstacle detection",
        "Acrylic body",
        "Low clearance",
        "Status lights",
    ]
    for i, item in enumerate(safe):
        col, row = i % 3, i // 3
        x, y = 36 + col * 300, 120 + row * 150
        d.rect(s, x, y, 280, 120, WHITE, LINE)
        d.rect(s, x, y, 280, 6, ACCENT)
        d.text(s, x + 20, y + 40, 240, 50, item, 16, True, NAVY, 1)
    d.footer(s, "Slide 7 · Safety", False)

    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 18, 540, ACCENT)
    d.text(s, 50, 80, 860, 50, "First prototype", 32, True, WHITE, 1)
    d.text(
        s,
        50,
        160,
        860,
        120,
        "Interactive menu · waypoint travel ·\nspatial orientation · load carrying",
        24,
        False,
        SKY,
        1,
    )
    d.footer(s, "Slide 8 · Prototype", True)

    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Feedback and economics", 28, True, WHITE, 1)
    d.rect(s, 36, 120, 430, 300, NAVY)
    d.text(s, 56, 150, 390, 40, "Experts", 20, True, ACCENT, 1)
    d.text(
        s,
        56,
        210,
        390,
        160,
        "Positive aviation-industry feedback.\nAirport interest in further testing.",
        16,
        False,
        CREAM,
        1,
    )
    d.rect(s, 490, 120, 430, 300, WHITE, LINE)
    d.text(s, 510, 150, 390, 40, "Prototype cost", 20, True, NAVY, 1)
    d.text(s, 510, 220, 390, 60, "~ 90,000 RUB", 32, True, TEAL, 1)
    d.text(
        s,
        510,
        300,
        390,
        80,
        "Modular design — upgrade without full replacement.",
        15,
        False,
        MUTED,
        1,
    )
    d.footer(s, "Slides 9–10", False)

    s = d.blank()
    d.bg(s, CREAM)
    d.rect(s, 0, 0, 960, 70, NAVY)
    d.text(s, 36, 18, 800, 40, "Future plans", 28, True, WHITE, 1)
    plans = [
        "Metal frame and industrial Mecanum wheels",
        "Industrial electronics and sensing (incl. 360°)",
        "Passenger app and fleet dashboard",
        "Charging and service hub",
        "Real airport scenario trials",
    ]
    y = 110
    for i, p in enumerate(plans, 1):
        d.text(s, 50, y, 60, 36, f"{i:02d}", 18, True, TEAL, 1)
        d.text(s, 110, y, 800, 36, p, 17, False, INK, 1)
        y += 55
    d.footer(s, "Slide 11 · Future", False)

    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 18, 540, TEAL)
    d.pic(s, LOGO, 380, 80, 200, 52)
    d.text(s, 80, 200, 800, 60, "Thank you!", 40, True, WHITE, 2)
    d.text(s, 80, 280, 800, 40, "The AirPorter Team", 22, False, SKY, 2)
    d.text(s, 80, 400, 800, 30, "Questions welcome", 14, False, MUTED, 2)

    d.save(path)
    print("saved", path)


if __name__ == "__main__":
    build_ru(DESKTOP / "AirPorter Presentation (RU).pptx")
    build_en(DESKTOP / "AirPorter Presentation (EN).pptx")
    print("DONE")
