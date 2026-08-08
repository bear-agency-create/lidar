# -*- coding: utf-8 -*-
"""AirPorter decks — richer text, no airport logo, refined design."""
from __future__ import annotations

import os
from pathlib import Path

import win32com.client as win32

DESKTOP = Path(os.path.expanduser(r"~\Desktop"))
# Decorative plane only (no airport brand)
PLANE = Path(r"C:\Users\user\Projects\lidar\monitor\assets\realistic-airliner-balanced.png")


def rgb(r: int, g: int, b: int) -> int:
    return r + (g << 8) + (b << 16)


# Soft terminal palette — navy / slate / copper accent (not purple-AI)
NAVY = rgb(14, 28, 44)
NAVY2 = rgb(22, 42, 64)
SLATE = rgb(36, 54, 72)
TEAL = rgb(46, 150, 168)
SKY = rgb(120, 190, 210)
CREAM = rgb(248, 245, 240)
PAPER = rgb(255, 252, 248)
INK = rgb(22, 32, 42)
MUTED = rgb(95, 112, 128)
WHITE = rgb(255, 255, 255)
COPPER = rgb(184, 132, 74)
LINE = rgb(220, 226, 232)

PP_BLANK = 12
MSO_RECT = 1
T, F = -1, 0


class Deck:
    def __init__(self) -> None:
        self.ppt = win32.Dispatch("PowerPoint.Application")
        self.ppt.Visible = T
        self.pres = self.ppt.Presentations.Add()
        self.pres.PageSetup.SlideWidth = 960
        self.pres.PageSetup.SlideHeight = 540

    def blank(self):
        return self.pres.Slides.Add(self.pres.Slides.Count + 1, PP_BLANK)

    def bg(self, s, c):
        s.FollowMasterBackground = False
        s.Background.Fill.Solid()
        s.Background.Fill.ForeColor.RGB = c

    def rect(self, s, l, t, w, h, fill, line=None):
        # Rounded cards + subtle shadow; structural bars remain square.
        shape_type = 5 if line is not None else MSO_RECT
        sh = s.Shapes.AddShape(shape_type, l, t, w, h)
        sh.Fill.Solid()
        sh.Fill.ForeColor.RGB = fill
        if line is None:
            sh.Line.Visible = F
        else:
            sh.Line.ForeColor.RGB = line
            sh.Line.Weight = 0.75
            try:
                sh.Shadow.Visible = T
                sh.Shadow.ForeColor.RGB = rgb(120, 130, 140)
                sh.Shadow.Transparency = 82
                sh.Shadow.OffsetX = 2
                sh.Shadow.OffsetY = 3
            except Exception:
                pass
        return sh

    def text(self, s, l, t, w, h, txt, size, bold, color, align=1):
        tb = s.Shapes.AddTextbox(1, l, t, w, h)
        tr = tb.TextFrame.TextRange
        tr.Text = txt
        tr.Font.Name = "Calibri"
        tr.Font.Size = size
        tr.Font.Bold = T if bold else F
        tr.Font.Color.RGB = color
        tr.ParagraphFormat.Alignment = align
        # slightly tighter leading for denser slides
        try:
            tr.ParagraphFormat.SpaceWithin = 1.05
        except Exception:
            pass
        tb.TextFrame.WordWrap = T
        tb.TextFrame.MarginLeft = 4
        tb.TextFrame.MarginRight = 4
        return tb

    def pic(self, s, path: Path, l, t, w, h):
        if path.is_file():
            try:
                s.Shapes.AddPicture(str(path), F, T, l, t, w, h)
            except Exception:
                pass

    def circle(self, s, x, y, size, fill, line=None, transparency=0):
        sh = s.Shapes.AddShape(9, x, y, size, size)  # msoShapeOval
        sh.Fill.Solid()
        sh.Fill.ForeColor.RGB = fill
        sh.Fill.Transparency = transparency
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

    def header(self, s, title: str, subtitle: str | None = None):
        self.rect(s, 0, 0, 960, 78, NAVY)
        self.rect(s, 0, 0, 10, 78, COPPER)
        self.rect(s, 10, 76, 950, 2, TEAL)
        self.text(s, 36, 12, 700, 36, title, 26, True, WHITE, 1)
        if subtitle:
            self.text(s, 36, 46, 800, 24, subtitle, 12, False, SKY, 1)
        # Flight-board style slide badge.
        self.rect(s, 810, 18, 54, 38, NAVY2, TEAL)
        self.text(s, 810, 26, 54, 20, f"{s.SlideIndex:02d}", 11, True, SKY, 2)
        self.text(s, 870, 22, 65, 28, "AIR", 11, True, TEAL, 3)

    def footer(self, s, label: str, dark=False):
        c = SKY if dark else MUTED
        self.line(s, 30, 505, 930, 505, c, 0.7)
        self.text(s, 30, 512, 700, 22, label, 10, False, c, 1)
        self.text(s, 860, 512, 70, 22, f"{s.SlideIndex:02d}", 10, True, c, 3)

    def save(self, path: Path):
        if path.exists():
            path.unlink()
        self.pres.SaveAs(str(path))
        self.pres.Close()
        self.ppt.Quit()


def build_ru(path: Path) -> None:
    d = Deck()

    # 1 Title
    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 14, 540, COPPER)
    d.rect(s, 0, 460, 960, 80, NAVY2)
    # Aircraft sits inside a glass-like instrument panel.
    d.rect(s, 620, 35, 310, 350, NAVY2, SLATE)
    d.text(s, 640, 55, 260, 18, "FLIGHT ASSISTANCE / 01", 9, True, SKY, 1)
    d.line(s, 645, 338, 900, 338, TEAL, 1.2, True)
    d.circle(s, 640, 331, 14, COPPER)
    d.circle(s, 892, 331, 14, TEAL)
    # Keep the top-view aircraft at its native aspect ratio (not stretched).
    d.pic(s, PLANE, 670, 75, 210, 237)
    d.text(s, 48, 100, 460, 60, "AirPorter", 44, True, WHITE, 1)
    d.text(
        s,
        48,
        165,
        460,
        90,
        "Мобильный робот-ассистент\nдля аэропорта",
        24,
        False,
        SKY,
        1,
    )
    d.text(
        s,
        48,
        280,
        460,
        70,
        "Делаем путь пассажира в терминале\nпонятнее, спокойнее и легче.",
        15,
        False,
        CREAM,
        1,
    )
    d.rect(s, 48, 375, 135, 34, NAVY2, TEAL)
    d.text(s, 48, 383, 135, 20, "НАВИГАЦИЯ", 10, True, SKY, 2)
    d.rect(s, 195, 375, 135, 34, NAVY2, TEAL)
    d.text(s, 195, 383, 135, 20, "ESCORT", 10, True, SKY, 2)
    d.rect(s, 342, 375, 135, 34, NAVY2, COPPER)
    d.text(s, 342, 383, 135, 20, "БАГАЖ", 10, True, COPPER, 2)
    d.text(s, 640, 355, 260, 18, "TERMINAL ROUTE · ACTIVE", 9, False, MUTED, 1)
    d.text(s, 48, 480, 700, 40, "Презентация проекта · команда AirPorter", 14, False, MUTED, 1)

    # 2 Intro / goal
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "О проекте", "Зачем нужен AirPorter")
    d.text(
        s,
        36,
        100,
        880,
        120,
        "AirPorter — мобильный робот-ассистент для аэропорта. Цель проекта — сделать пребывание пассажиров более комфортным: помочь сориентироваться в терминале, сопроводить до нужной точки и при необходимости перевезти багаж, снизив физическую нагрузку и стресс — особенно для тех, кто в аэропорту впервые.",
        16,
        False,
        INK,
        1,
    )
    d.rect(s, 36, 250, 280, 200, WHITE, LINE)
    d.rect(s, 36, 250, 280, 6, TEAL)
    d.text(s, 52, 275, 250, 40, "Ориентация", 18, True, NAVY, 1)
    d.text(s, 52, 320, 250, 100, "Подсказки по маршруту и сервисам прямо на экране робота.", 14, False, MUTED, 1)
    d.rect(s, 340, 250, 280, 200, WHITE, LINE)
    d.rect(s, 340, 250, 280, 6, TEAL)
    d.text(s, 356, 275, 250, 40, "Сопровождение", 18, True, NAVY, 1)
    d.text(s, 356, 320, 250, 100, "Робот ведёт пассажира к выбранной точке: регистрация, выход, сервисы.", 14, False, MUTED, 1)
    d.rect(s, 644, 250, 280, 200, WHITE, LINE)
    d.rect(s, 644, 250, 280, 6, COPPER)
    d.text(s, 660, 275, 250, 40, "Багаж", 18, True, NAVY, 1)
    d.text(s, 660, 320, 250, 100, "Перевозка вещей и помощь на этапах проверки багажа.", 14, False, MUTED, 1)
    d.footer(s, "Слайд 1–2 · Знакомство")

    # 3 Problem
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Проблема", "Что мешает пассажиру в современном аэропорту")
    d.text(
        s,
        36,
        100,
        880,
        80,
        "Аэропорт — сложная система с большим объёмом информации, сервисов и зон. Для многих пассажиров, особенно иностранных или редко летающих, ориентирование становится серьёзной задачей.",
        15,
        False,
        INK,
        1,
    )
    items = [
        ("01", "Физическая нагрузка", "Перевозка багажа по длинным переходам терминала утомляет и отвлекает от маршрута."),
        ("02", "Сложная навигация", "Много зон и указателей: легко ошибиться с выходом, стойкой или сервисом."),
        ("03", "Языковой барьер", "Сложно быстро получить понятную информацию на привычном языке."),
    ]
    y = 200
    for n, t, desc in items:
        d.rect(s, 36, y, 70, 70, NAVY)
        d.text(s, 46, y + 18, 50, 40, n, 16, True, COPPER, 2)
        d.rect(s, 116, y, 808, 70, WHITE, LINE)
        d.text(s, 136, y + 10, 770, 28, t, 16, True, NAVY, 1)
        d.text(s, 136, y + 36, 770, 28, desc, 13, False, MUTED, 1)
        y += 85
    d.footer(s, "Слайд 2 · Проблема")

    # 4 Solution overview
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Решение", "Как работает AirPorter")
    d.text(
        s,
        36,
        95,
        880,
        55,
        "Мы предлагаем робота-ассистента, который помогает пассажиру пройти путь от стартовой точки до пункта назначения с учётом его потребностей. Работа системы идёт в несколько этапов.",
        14,
        False,
        INK,
        1,
    )
    d.rect(s, 36, 165, 430, 280, NAVY)
    d.text(s, 56, 185, 390, 30, "Этап 1 · Сканирование билета", 15, True, COPPER, 1)
    d.text(
        s,
        56,
        230,
        390,
        180,
        "Робот получает основную информацию о пассажире и рейсе. Это точка входа в сервис: дальше система понимает, куда человеку нужно и какие сценарии предложить.",
        14,
        False,
        CREAM,
        1,
    )
    d.rect(s, 490, 165, 430, 280, WHITE, LINE)
    d.text(s, 510, 185, 390, 30, "Этап 2 · Информация на экране", 15, True, NAVY, 1)
    d.text(
        s,
        510,
        230,
        390,
        180,
        "На экране отображаются номер рейса, время посадки, выход и доступные сервисы. Пассажир сразу видит понятный следующий шаг — без поиска по терминалу.",
        14,
        False,
        MUTED,
        1,
    )
    d.footer(s, "Слайд 3 · Решение")

    # 5 Scenarios
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Три сценария", "Пассажир выбирает нужный формат помощи")
    scenarios = [
        (
            "1",
            "Только информация",
            "Пассажиру нужна только информация. Робот показывает маршрут и необходимые данные, после чего сессия завершается. Быстрый ответ без движения по терминалу.",
        ),
        (
            "2",
            "Сопровождение",
            "Пассажиру требуется escort. Робот предлагает маршрут с учётом выбранных точек: регистрация, туалет, Duty Free, кафе или выход на посадку. После выбора робот сопровождает человека.",
        ),
        (
            "3",
            "Только багаж",
            "Нужна помощь только перевозкой багажа. Робот берёт вещи и проходит этапы проверки багажа; клиенту остаётся пройти личный досмотр и сесть в самолёт.",
        ),
    ]
    y = 95
    for n, t, desc in scenarios:
        d.rect(s, 36, y, 56, 100, TEAL if n != "3" else COPPER)
        d.text(s, 44, y + 30, 40, 40, n, 22, True, WHITE, 2)
        d.rect(s, 102, y, 822, 100, WHITE, LINE)
        d.text(s, 122, y + 12, 780, 28, t, 16, True, NAVY, 1)
        d.text(s, 122, y + 42, 780, 50, desc, 12, False, MUTED, 1)
        y += 115
    d.footer(s, "Слайд 3 · Сценарии")

    # 6 Hardware
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Аппаратная платформа", "Первый рабочий прототип")
    d.text(
        s,
        36,
        95,
        880,
        50,
        "Для реализации проекта собрана рабочая платформа: бортовой компьютер, привод, сенсоры и пассажирский экран.",
        14,
        False,
        INK,
        1,
    )
    blocks = [
        ("Raspberry Pi 5 (16 ГБ)", "ROS 2 Jazzy, обработка лидара и камеры, высокоуровневая логика робота."),
        ("Arduino Mega 2560", "Сигналы энкодеров и управление двигателями для точного движения платформы."),
        ("Привод Mecanum", "Драйверы L298N, моторы JGB37-520, омни-колёса для манёвров в терминале."),
        ("Сенсоры и UI", "Лидар COIN D6, камера, сенсорный экран 10,1\" для киоска пассажира."),
    ]
    coords = [(36, 160), (490, 160), (36, 320), (490, 320)]
    for (x, y), (t, desc) in zip(coords, blocks):
        d.rect(s, x, y, 430, 130, WHITE, LINE)
        d.rect(s, x, y, 8, 130, TEAL)
        d.text(s, x + 22, y + 18, 390, 32, t, 15, True, NAVY, 1)
        d.text(s, x + 22, y + 55, 390, 60, desc, 12, False, MUTED, 1)
    d.footer(s, "Слайд 4 · Железо")

    # 7 System architecture — additional detail and visual flow.
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Как устроена система", "От сенсоров до движения и интерфейса")
    d.text(
        s,
        36,
        95,
        880,
        58,
        "AirPorter разделён на уровни: сенсоры собирают данные, Raspberry Pi строит карту и принимает решения, а Arduino выполняет команды движения. Пассажир и оператор получают разные, но связанные интерфейсы.",
        13,
        False,
        INK,
        1,
    )
    flow = [
        ("01", "Сенсоры", "Лидар, камера,\nэнкодеры"),
        ("02", "ROS 2 / Pi 5", "Карта, поза,\nмаршрут, логика"),
        ("03", "Arduino Mega", "Моторы, плавный\nстарт и стоп"),
        ("04", "Интерфейсы", "Киоск пассажира\nи админ-панель"),
    ]
    x = 36
    for i, (n, title, desc) in enumerate(flow):
        d.rect(s, x, 195, 200, 220, WHITE, LINE)
        d.text(s, x + 16, 215, 45, 28, n, 15, True, COPPER, 1)
        d.text(s, x + 16, 260, 168, 34, title, 16, True, NAVY, 1)
        d.text(s, x + 16, 315, 168, 70, desc, 13, False, MUTED, 1)
        if i < 3:
            d.text(s, x + 202, 275, 28, 40, "→", 24, True, TEAL, 2)
        x += 228
    d.text(
        s,
        36,
        445,
        880,
        42,
        "Такое разделение упрощает диагностику, позволяет безопасно остановить платформу при потере связи и постепенно заменять компоненты на промышленные.",
        12,
        False,
        MUTED,
        1,
    )
    d.footer(s, "Архитектура системы")

    # 8 Navigation
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Навигация", "Карта, поза, маршрут")
    d.text(
        s,
        36,
        95,
        880,
        70,
        "Реализована система построения карты помещения с помощью лидара. Робот определяет своё положение, учитывает габариты корпуса и данные энкодеров, строит маршрут и объезжает препятствия.",
        14,
        False,
        INK,
        1,
    )
    points = [
        ("Карта по лидару", "Построение и обновление карты окружения в терминале."),
        ("Поза и габариты", "Учёт размера корпуса и показаний энкодеров."),
        ("Маршрут", "Планирование пути и объезд препятствий."),
        ("Точки + оператор", "Проезд по waypoints и ручной контроль при необходимости."),
    ]
    x = 36
    for t, desc in points:
        d.rect(s, x, 190, 210, 250, NAVY)
        d.rect(s, x, 190, 210, 6, COPPER)
        d.text(s, x + 14, 220, 180, 60, t, 14, True, WHITE, 1)
        d.text(s, x + 14, 300, 180, 110, desc, 12, False, SKY, 1)
        x += 228
    d.footer(s, "Слайд 5 · Навигация")

    # 8 Interface
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Интерфейс", "Киоск для пассажира")
    d.text(
        s,
        36,
        95,
        880,
        70,
        "На главном экране — основные сервисы аэропорта: регистрация, посадка, выдача багажа, информационная стойка и другие точки терминала. Интерфейс сделан простым и «аэропортовым» по визуалу.",
        14,
        False,
        INK,
        1,
    )
    d.rect(s, 36, 185, 560, 260, WHITE, LINE)
    d.text(s, 56, 210, 520, 30, "Что видит пассажир", 16, True, NAVY, 1)
    d.text(
        s,
        56,
        255,
        520,
        160,
        "• выбор нужного сервиса или точки маршрута\n• информация по рейсу после скана билета\n• понятные сценарии: инфо / escort / багаж\n• крупные элементы управления для сенсорного экрана",
        14,
        False,
        MUTED,
        1,
    )
    d.rect(s, 620, 185, 300, 75, NAVY)
    d.text(s, 620, 205, 300, 40, "Русский", 18, True, WHITE, 2)
    d.rect(s, 620, 275, 300, 75, NAVY2)
    d.text(s, 620, 295, 300, 40, "English", 18, True, WHITE, 2)
    d.rect(s, 620, 365, 300, 75, SLATE)
    d.text(s, 620, 385, 300, 40, "Татарча", 18, True, WHITE, 2)
    d.footer(s, "Слайд 6 · Интерфейс")

    # 9 Safety
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Безопасность", "Защита пассажира и платформы")
    d.text(
        s,
        36,
        95,
        880,
        45,
        "В прототипе заложены базовые меры безопасности для работы рядом с людьми в терминале.",
        14,
        False,
        INK,
        1,
    )
    safe = [
        ("Связь", "Автоматическая остановка при потере связи с управлением."),
        ("Маршрут", "Контроль следования по заданному пути."),
        ("Препятствия", "Распознавание препятствий по данным сенсоров."),
        ("Корпус", "Защитный корпус из оргстекла."),
        ("Клиренс", "Небольшой дорожный просвет для устойчивости."),
        ("Индикация", "Световая индикация состояния робота."),
    ]
    for i, (t, desc) in enumerate(safe):
        col, row = i % 3, i // 3
        x, y = 36 + col * 300, 160 + row * 145
        d.rect(s, x, y, 280, 125, WHITE, LINE)
        d.rect(s, x, y, 280, 5, COPPER)
        d.text(s, x + 16, y + 20, 250, 28, t, 15, True, NAVY, 1)
        d.text(s, x + 16, y + 55, 250, 55, desc, 12, False, MUTED, 1)
    d.footer(s, "Слайд 7 · Безопасность")

    # 10 Prototype now
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Первый прототип", "Что уже реализовано")
    d.text(
        s,
        36,
        100,
        880,
        70,
        "Сейчас команда представляет первый прототип: платформа уже демонстрирует ключевые функции продукта и готова к дальнейшей доработке.",
        15,
        False,
        INK,
        1,
    )
    now = [
        "Интерактивное меню на сенсорном экране",
        "Проезд по заданным точкам маршрута",
        "Ориентирование в пространстве по карте и сенсорам",
        "Возможность перевозить груз",
    ]
    y = 190
    for i, line in enumerate(now, 1):
        d.rect(s, 36, y, 48, 48, NAVY)
        d.text(s, 44, y + 10, 32, 30, str(i), 16, True, COPPER, 2)
        d.rect(s, 96, y, 828, 48, WHITE, LINE)
        d.text(s, 116, y + 12, 790, 30, line, 15, False, INK, 1)
        y += 62
    d.footer(s, "Слайд 8 · Прототип")

    # 11 Experts + money
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Оценка и экономика", "Обратная связь и стоимость")
    d.rect(s, 36, 110, 440, 340, NAVY)
    d.text(s, 56, 140, 400, 36, "Экспертная оценка", 18, True, COPPER, 1)
    d.text(
        s,
        56,
        195,
        400,
        220,
        "Проект представлен экспертам авиационной отрасли и получил положительную оценку. Представители аэропорта выразили заинтересованность в дальнейшем тестировании разработки.",
        14,
        False,
        CREAM,
        1,
    )
    d.rect(s, 500, 110, 424, 340, WHITE, LINE)
    d.text(s, 520, 140, 380, 36, "Экономика прототипа", 18, True, NAVY, 1)
    d.text(s, 520, 210, 380, 50, "~ 90 000 ₽", 32, True, TEAL, 1)
    d.text(
        s,
        520,
        280,
        380,
        140,
        "Стоимость текущего прототипа — около девяноста тысяч рублей. Модульная конструкция позволяет модернизировать систему без полной замены оборудования.",
        13,
        False,
        MUTED,
        1,
    )
    d.footer(s, "Слайды 9–10")

    # 12 Future
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Планы на будущее", "Масштабная, но поэтапная дорожная карта")
    d.text(
        s,
        36,
        95,
        880,
        45,
        "Впереди большая работа: усиление конструкции, промышленные компоненты, сервисы сопровождения флота и испытания в реальных сценариях.",
        13,
        False,
        INK,
        1,
    )
    plans = [
        "Усиление каркаса металлическими профилями и промышленные колёса Mecanum",
        "Переход на промышленную электронику и усиление сенсорики, включая камеру 360°",
        "Приложение для пассажира и панель флота для команды разработки",
        "Хаб зарядки и обслуживания роботов",
        "Испытания системы в реальных ситуациях аэропорта",
    ]
    y = 155
    for i, p in enumerate(plans, 1):
        d.text(s, 40, y, 50, 28, f"{i:02d}", 14, True, TEAL, 1)
        d.text(s, 95, y, 820, 40, p, 13, False, INK, 1)
        y += 52
    d.footer(s, "Слайд 11 · Планы")

    # 13 Close
    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 14, 540, COPPER)
    d.text(s, 80, 180, 800, 60, "Спасибо за внимание!", 36, True, WHITE, 2)
    d.text(s, 80, 260, 800, 40, "Команда AirPorter", 22, False, SKY, 2)
    d.text(
        s,
        120,
        340,
        720,
        60,
        "Готовы ответить на вопросы о сценариях, прототипе и планах развития.",
        14,
        False,
        MUTED,
        2,
    )

    d.save(path)
    print("saved", path)


def build_en(path: Path) -> None:
    d = Deck()

    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 14, 540, COPPER)
    d.rect(s, 0, 460, 960, 80, NAVY2)
    d.rect(s, 620, 35, 310, 350, NAVY2, SLATE)
    d.text(s, 640, 55, 260, 18, "FLIGHT ASSISTANCE / 01", 9, True, SKY, 1)
    d.line(s, 645, 338, 900, 338, TEAL, 1.2, True)
    d.circle(s, 640, 331, 14, COPPER)
    d.circle(s, 892, 331, 14, TEAL)
    # Keep the aircraft narrow and proportional.
    d.pic(s, PLANE, 670, 75, 210, 237)
    d.text(s, 48, 100, 460, 60, "AirPorter", 44, True, WHITE, 1)
    d.text(s, 48, 165, 460, 90, "A mobile robot assistant\nfor the airport", 24, False, SKY, 1)
    d.text(s, 48, 280, 460, 70, "Making the passenger journey\nclearer, calmer, and easier.", 15, False, CREAM, 1)
    d.rect(s, 48, 375, 135, 34, NAVY2, TEAL)
    d.text(s, 48, 383, 135, 20, "NAVIGATION", 10, True, SKY, 2)
    d.rect(s, 195, 375, 135, 34, NAVY2, TEAL)
    d.text(s, 195, 383, 135, 20, "ESCORT", 10, True, SKY, 2)
    d.rect(s, 342, 375, 135, 34, NAVY2, COPPER)
    d.text(s, 342, 383, 135, 20, "LUGGAGE", 10, True, COPPER, 2)
    d.text(s, 640, 355, 260, 18, "TERMINAL ROUTE · ACTIVE", 9, False, MUTED, 1)
    d.text(s, 48, 480, 700, 40, "Project presentation · AirPorter team", 14, False, MUTED, 1)

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "About the project", "Why AirPorter exists")
    d.text(
        s,
        36,
        100,
        880,
        120,
        "AirPorter is a mobile robot assistant for airports. The goal is to make passengers’ time more comfortable: help them navigate the terminal, escort them to the right place, and when needed carry luggage — reducing strain and stress, especially for first-time visitors.",
        15,
        False,
        INK,
        1,
    )
    cards = [
        ("Guidance", "Routes and services shown on the robot screen."),
        ("Escort", "The robot leads the passenger to a chosen point."),
        ("Luggage", "Carrying bags and helping through baggage flow."),
    ]
    x = 36
    for t, desc in cards:
        d.rect(s, x, 250, 280, 200, WHITE, LINE)
        d.rect(s, x, 250, 280, 6, TEAL)
        d.text(s, x + 16, 275, 250, 40, t, 18, True, NAVY, 1)
        d.text(s, x + 16, 325, 250, 100, desc, 14, False, MUTED, 1)
        x += 300
    d.footer(s, "Slides 1–2 · Introduction")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "The problem", "What makes airports hard for passengers")
    d.text(
        s,
        36,
        100,
        880,
        70,
        "A modern airport is a complex system of information, services, and zones. For many passengers — especially international or infrequent flyers — orientation becomes a serious challenge.",
        14,
        False,
        INK,
        1,
    )
    items = [
        ("01", "Physical strain", "Carrying luggage across long terminal routes is tiring and distracting."),
        ("02", "Complex navigation", "Many zones and signs make it easy to miss a gate, desk, or service."),
        ("03", "Language barrier", "Getting clear information quickly in a familiar language is hard."),
    ]
    y = 195
    for n, t, desc in items:
        d.rect(s, 36, y, 70, 70, NAVY)
        d.text(s, 46, y + 18, 50, 40, n, 16, True, COPPER, 2)
        d.rect(s, 116, y, 808, 70, WHITE, LINE)
        d.text(s, 136, y + 10, 770, 28, t, 16, True, NAVY, 1)
        d.text(s, 136, y + 36, 770, 28, desc, 13, False, MUTED, 1)
        y += 85
    d.footer(s, "Slide 2 · Problem")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "The solution", "How AirPorter works")
    d.text(
        s,
        36,
        95,
        880,
        55,
        "We propose a robot assistant that helps a passenger travel from a starting point to a destination according to their needs. The system works in stages.",
        14,
        False,
        INK,
        1,
    )
    d.rect(s, 36, 165, 430, 280, NAVY)
    d.text(s, 56, 185, 390, 30, "Stage 1 · Ticket scan", 15, True, COPPER, 1)
    d.text(
        s,
        56,
        230,
        390,
        180,
        "The robot receives key passenger and flight data. This is the entry point: the system then knows where the person needs to go and which scenarios to offer.",
        14,
        False,
        CREAM,
        1,
    )
    d.rect(s, 490, 165, 430, 280, WHITE, LINE)
    d.text(s, 510, 185, 390, 30, "Stage 2 · On-screen information", 15, True, NAVY, 1)
    d.text(
        s,
        510,
        230,
        390,
        180,
        "The screen shows flight number, boarding time, gate, and available services. The passenger immediately sees a clear next step — without searching the terminal alone.",
        14,
        False,
        MUTED,
        1,
    )
    d.footer(s, "Slide 3 · Solution")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Three scenarios", "The passenger chooses the type of help")
    scenarios = [
        ("1", "Information only", "The passenger only needs information. The robot shows the route and required data, then the session ends."),
        ("2", "Escort", "The robot suggests a route via check-in, restrooms, Duty Free, café, or the boarding gate, then escorts the passenger."),
        ("3", "Luggage only", "The robot takes the bags through baggage screening; the passenger only completes personal security and boards."),
    ]
    y = 95
    for n, t, desc in scenarios:
        d.rect(s, 36, y, 56, 100, TEAL if n != "3" else COPPER)
        d.text(s, 44, y + 30, 40, 40, n, 22, True, WHITE, 2)
        d.rect(s, 102, y, 822, 100, WHITE, LINE)
        d.text(s, 122, y + 12, 780, 28, t, 16, True, NAVY, 1)
        d.text(s, 122, y + 42, 780, 50, desc, 12, False, MUTED, 1)
        y += 115
    d.footer(s, "Slide 3 · Scenarios")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Hardware platform", "First working prototype")
    d.text(
        s,
        36,
        95,
        880,
        45,
        "A working platform is assembled: onboard computer, drive system, sensors, and passenger display.",
        14,
        False,
        INK,
        1,
    )
    blocks = [
        ("Raspberry Pi 5 (16 GB)", "ROS 2 Jazzy, lidar and camera processing, high-level robot logic."),
        ("Arduino Mega 2560", "Encoder signals and motor control for precise platform motion."),
        ("Mecanum drive", "L298N drivers, JGB37-520 motors, omni wheels for terminal maneuvers."),
        ("Sensors & UI", "COIN D6 lidar, camera, 10.1\" touchscreen for the passenger kiosk."),
    ]
    coords = [(36, 160), (490, 160), (36, 320), (490, 320)]
    for (x, y), (t, desc) in zip(coords, blocks):
        d.rect(s, x, y, 430, 130, WHITE, LINE)
        d.rect(s, x, y, 8, 130, TEAL)
        d.text(s, x + 22, y + 18, 390, 32, t, 15, True, NAVY, 1)
        d.text(s, x + 22, y + 55, 390, 60, desc, 12, False, MUTED, 1)
    d.footer(s, "Slide 4 · Hardware")

    # System architecture
    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "System architecture", "From sensing to motion and user experience")
    d.text(
        s,
        36,
        95,
        880,
        58,
        "AirPorter is split into layers: sensors collect data, Raspberry Pi builds the map and makes high-level decisions, while Arduino executes motion commands. Passenger and operator use separate but connected interfaces.",
        13,
        False,
        INK,
        1,
    )
    flow = [
        ("01", "Sensors", "Lidar, camera,\nencoders"),
        ("02", "ROS 2 / Pi 5", "Map, pose, route,\nhigh-level logic"),
        ("03", "Arduino Mega", "Motors, smooth\nstart and stop"),
        ("04", "Interfaces", "Passenger kiosk\nand admin panel"),
    ]
    x = 36
    for i, (n, title, desc) in enumerate(flow):
        d.rect(s, x, 195, 200, 220, WHITE, LINE)
        d.text(s, x + 16, 215, 45, 28, n, 15, True, COPPER, 1)
        d.text(s, x + 16, 260, 168, 34, title, 16, True, NAVY, 1)
        d.text(s, x + 16, 315, 168, 70, desc, 13, False, MUTED, 1)
        if i < 3:
            d.text(s, x + 202, 275, 28, 40, "→", 24, True, TEAL, 2)
        x += 228
    d.text(
        s,
        36,
        445,
        880,
        42,
        "This separation simplifies diagnostics, enables a safe stop on link loss, and allows components to be upgraded to industrial versions step by step.",
        12,
        False,
        MUTED,
        1,
    )
    d.footer(s, "System architecture")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Navigation", "Map, pose, route")
    d.text(
        s,
        36,
        95,
        880,
        70,
        "Indoor mapping is built with lidar. The robot estimates pose, accounts for footprint and encoders, plans a route, and avoids obstacles.",
        14,
        False,
        INK,
        1,
    )
    points = [
        ("Lidar map", "Build and update the environment map."),
        ("Pose & size", "Footprint awareness plus encoder data."),
        ("Routing", "Path planning and obstacle avoidance."),
        ("Waypoints", "Point-to-point travel and operator control."),
    ]
    x = 36
    for t, desc in points:
        d.rect(s, x, 190, 210, 250, NAVY)
        d.rect(s, x, 190, 210, 6, COPPER)
        d.text(s, x + 14, 220, 180, 60, t, 14, True, WHITE, 1)
        d.text(s, x + 14, 300, 180, 110, desc, 12, False, SKY, 1)
        x += 228
    d.footer(s, "Slide 5 · Navigation")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Interface", "Passenger kiosk")
    d.text(
        s,
        36,
        95,
        880,
        70,
        "The home screen presents airport services: check-in, boarding, baggage claim, information desk, and other terminal points. The UI is simple and airport-themed.",
        14,
        False,
        INK,
        1,
    )
    d.rect(s, 36, 185, 560, 260, WHITE, LINE)
    d.text(s, 56, 210, 520, 30, "What the passenger sees", 16, True, NAVY, 1)
    d.text(
        s,
        56,
        255,
        520,
        160,
        "• choose a service or route point\n• flight info after ticket scan\n• clear scenarios: info / escort / luggage\n• large touch targets for the screen",
        14,
        False,
        MUTED,
        1,
    )
    for i, lang in enumerate(("Russian", "English", "Tatar")):
        y = 185 + i * 90
        d.rect(s, 620, y, 300, 75, NAVY if i == 0 else (NAVY2 if i == 1 else SLATE))
        d.text(s, 620, y + 20, 300, 40, lang, 18, True, WHITE, 2)
    d.footer(s, "Slide 6 · Interface")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Safety", "Protecting people and the platform")
    d.text(
        s,
        36,
        95,
        880,
        40,
        "The prototype includes basic safety measures for operation near people in a terminal.",
        14,
        False,
        INK,
        1,
    )
    safe = [
        ("Link", "Automatic stop on loss of control connection."),
        ("Route", "Monitoring travel along the planned path."),
        ("Obstacles", "Obstacle recognition from sensor data."),
        ("Body", "Protective acrylic enclosure."),
        ("Clearance", "Low ground clearance for stability."),
        ("Lights", "Status lighting for robot state."),
    ]
    for i, (t, desc) in enumerate(safe):
        col, row = i % 3, i // 3
        x, y = 36 + col * 300, 155 + row * 145
        d.rect(s, x, y, 280, 125, WHITE, LINE)
        d.rect(s, x, y, 280, 5, COPPER)
        d.text(s, x + 16, y + 20, 250, 28, t, 15, True, NAVY, 1)
        d.text(s, x + 16, y + 55, 250, 55, desc, 12, False, MUTED, 1)
    d.footer(s, "Slide 7 · Safety")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "First prototype", "What already works")
    d.text(
        s,
        36,
        100,
        880,
        60,
        "We present the team’s first prototype: the platform already demonstrates core product functions and is ready for further refinement.",
        14,
        False,
        INK,
        1,
    )
    now = [
        "Interactive menu on the touchscreen",
        "Travel along defined waypoints",
        "Spatial orientation via map and sensors",
        "Ability to carry a load",
    ]
    y = 185
    for i, line in enumerate(now, 1):
        d.rect(s, 36, y, 48, 48, NAVY)
        d.text(s, 44, y + 10, 32, 30, str(i), 16, True, COPPER, 2)
        d.rect(s, 96, y, 828, 48, WHITE, LINE)
        d.text(s, 116, y + 12, 790, 30, line, 15, False, INK, 1)
        y += 62
    d.footer(s, "Slide 8 · Prototype")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Feedback and economics", "Validation and cost")
    d.rect(s, 36, 110, 440, 340, NAVY)
    d.text(s, 56, 140, 400, 36, "Expert feedback", 18, True, COPPER, 1)
    d.text(
        s,
        56,
        195,
        400,
        220,
        "The project was presented to aviation-industry experts and received positive feedback. Airport representatives expressed interest in further testing.",
        14,
        False,
        CREAM,
        1,
    )
    d.rect(s, 500, 110, 424, 340, WHITE, LINE)
    d.text(s, 520, 140, 380, 36, "Prototype economics", 18, True, NAVY, 1)
    d.text(s, 520, 210, 380, 50, "~ 90,000 RUB", 30, True, TEAL, 1)
    d.text(
        s,
        520,
        280,
        380,
        140,
        "Current prototype cost is about ninety thousand rubles. Modular design allows upgrades without fully replacing the hardware.",
        13,
        False,
        MUTED,
        1,
    )
    d.footer(s, "Slides 9–10")

    s = d.blank()
    d.bg(s, CREAM)
    d.header(s, "Future plans", "Ambitious, staged roadmap")
    d.text(
        s,
        36,
        95,
        880,
        45,
        "Ahead: stronger structure, industrial components, fleet services, and real airport scenario trials.",
        13,
        False,
        INK,
        1,
    )
    plans = [
        "Reinforce the frame with metal profiles and industrial Mecanum wheels",
        "Move to industrial electronics and stronger sensing, including 360° camera",
        "Passenger app and developer fleet dashboard",
        "Charging and service hub for the robot fleet",
        "Testing the system in real airport situations",
    ]
    y = 155
    for i, p in enumerate(plans, 1):
        d.text(s, 40, y, 50, 28, f"{i:02d}", 14, True, TEAL, 1)
        d.text(s, 95, y, 820, 40, p, 13, False, INK, 1)
        y += 52
    d.footer(s, "Slide 11 · Future")

    s = d.blank()
    d.bg(s, NAVY)
    d.rect(s, 0, 0, 14, 540, COPPER)
    d.text(s, 80, 180, 800, 60, "Thank you!", 40, True, WHITE, 2)
    d.text(s, 80, 260, 800, 40, "The AirPorter Team", 22, False, SKY, 2)
    d.text(
        s,
        120,
        340,
        720,
        60,
        "Happy to answer questions about scenarios, the prototype, and the roadmap.",
        14,
        False,
        MUTED,
        2,
    )

    d.save(path)
    print("saved", path)


if __name__ == "__main__":
    build_ru(DESKTOP / "AirPorter Presentation RU v4.pptx")
    build_en(DESKTOP / "AirPorter Presentation EN v4.pptx")
    print("DONE")
