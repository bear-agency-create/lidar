# -*- coding: utf-8 -*-
"""Build calm, material-driven AirPorter presentations in RU and EN (PDF only)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps
import win32com.client as win32

DESKTOP = Path.home() / "Desktop"
MATERIALS = DESKTOP / "материал для AirPorter"
SOURCE_LOGO = MATERIALS / "AIRPORTER_logo.png"
SOURCE_PHOTO = MATERIALS / "photo_2026-08-07_13-37-15.jpg"
OUT_RU = DESKTOP / "AirPorter — Presentation RU.pdf"
OUT_EN = DESKTOP / "AirPorter — Presentation EN.pdf"


def rgb(r: int, g: int, b: int) -> int:
    return r + (g << 8) + (b << 16)


NAVY = rgb(13, 42, 68)
NAVY_SOFT = rgb(28, 63, 91)
BLUE = rgb(43, 137, 190)
TEAL = rgb(71, 166, 165)
AMBER = rgb(224, 157, 65)
INK = rgb(28, 48, 65)
MUTED = rgb(99, 119, 135)
PALE = rgb(246, 249, 251)
WHITE = rgb(255, 255, 255)
LINE = rgb(218, 228, 235)
LIGHT_BLUE = rgb(231, 242, 248)
LIGHT_TEAL = rgb(232, 244, 243)
LIGHT_AMBER = rgb(249, 241, 228)
TRUE, FALSE = -1, 0


RU = {
    "cover_title": "Мобильный робот-ассистент\nдля аэропорта",
    "cover_sub": "Навигация · сопровождение · помощь с багажом",
    "cover_note": "Рабочий инженерный прототип\nRaspberry Pi 5 · Arduino Mega · ROS 2",
    "team": "Илья Карякин · Станислав Парамонов · Артур Сабирзанов",
    "problem_title": "Почему пассажиру нужна помощь",
    "problem_sub": "Аэропорт хорошо организован как система, но может быть сложным для человека.",
    "problem_intro": "Большой объём информации, длинные переходы, контроль безопасности и поиск нужных зон создают стресс — особенно для тех, кто оказался в аэропорту впервые.",
    "problems": [
        ("Физическая нагрузка", "Багаж приходится перевозить по длинным маршрутам терминала."),
        ("Навигация", "Регистрация, контроль, сервисные точки и выход могут находиться далеко друг от друга."),
        ("Языковой барьер", "Иностранному пассажиру сложно быстро получить понятную помощь."),
    ],
    "solution_title": "Один понятный путь вместо множества вопросов",
    "solution_sub": "AirPorter начинает с потребности пассажира и превращает её в последовательный сценарий.",
    "solution_intro": "Робот объединяет билетный сценарий, информационный киоск, построение маршрута и мобильную платформу для перевозки вещей.",
    "steps": [
        ("01", "Сканирование", "Билет считывается камерой или данные вводятся вручную."),
        ("02", "Информация", "На экране отображаются рейс, время, выход и доступные сервисы."),
        ("03", "Выбор помощи", "Пассажир выбирает информацию, сопровождение или помощь с багажом."),
        ("04", "Маршрут", "Робот строит путь между заранее настроенными точками."),
    ],
    "modes_title": "Три сценария работы",
    "modes_sub": "Один интерфейс — разный объём помощи в зависимости от ситуации.",
    "modes": [
        ("Только информация", "Робот показывает данные рейса, нужную зону и путь. После этого сессия завершается."),
        ("Сопровождение", "Пассажир выбирает регистрацию, туалет, Duty Free, кафе или выход. Робот строит маршрут и ведёт человека."),
        ("Помощь с багажом", "Робот принимает вещи и следует по согласованному багажному сценарию. Интеграция с реальными процедурами аэропорта — следующий этап."),
    ],
    "hardware_title": "Аппаратная платформа",
    "hardware_sub": "Два уровня управления разделяют интерфейс и навигацию от управления приводом.",
    "hardware_note": "Реальный прототип собран на платформе 82 × 56 см. Открытая компоновка упрощает тестирование и модернизацию.",
    "hardware": [
        ("Raspberry Pi 5 · 16 ГБ", "ROS 2 Jazzy, карта, навигация, камера, киоск и админ-панель."),
        ("Arduino Mega 2560", "Моторы, энкодеры, watchdog и безопасная остановка."),
        ("4× Mecanum", "JGB37-520 + L298N: движение вперёд, назад, боком и разворот."),
        ("COIN D6 · камера · экран", "Карта препятствий, билетный сценарий и взаимодействие с пассажиром."),
    ],
    "nav_title": "Навигация с учётом размеров робота",
    "nav_sub": "Система уже объединяет карту, оценку положения, планирование и движение по точкам.",
    "nav_intro": "LiDAR сканирует помещение, энкодеры отслеживают движение, а собственный стек ROS 2 строит маршрут A→B с учётом корпуса 82 × 56 см.",
    "nav": [
        ("Карта", "Измерения LiDAR фильтруются и добавляются в карту препятствий."),
        ("Положение", "Одометрия и сопоставление сканов оценивают координаты и направление."),
        ("План", "Алгоритм A* ищет маршрут в свободном пространстве."),
        ("Движение", "Робот следует по точкам, сохраняя возможность ручной остановки."),
    ],
    "ui_title": "Интерфейс без лишней сложности",
    "ui_sub": "Крупные действия для пассажира и полный контроль для оператора.",
    "ui_flow": [
        ("1", "Выбрать язык", "Русский · английский · татарский"),
        ("2", "Выбрать сервис", "Регистрация · выход · багаж · информация"),
        ("3", "Считать билет", "Камера или ручной ввод"),
        ("4", "Начать помощь", "Информация · маршрут · сопровождение"),
    ],
    "ui_cards": [
        ("Киоск пассажира", "Понятный сенсорный интерфейс, билетный сценарий, выбор точки и статус маршрута."),
        ("Панель оператора", "Health, карта, STOP, миссия, логи и ручное управление для поддержки и тестирования."),
    ],
    "safety_title": "Безопасность начинается с остановки",
    "safety_sub": "Для сервисного робота предсказуемое поведение важнее максимальной скорости.",
    "safety": [
        ("Таймаут команд", "Нет корректной команды — привод останавливается."),
        ("Heartbeat киоска", "Потеря активной сессии отменяет сопровождение."),
        ("Контроль маршрута", "Движение ограничено картой и настроенными точками."),
        ("Карта препятствий", "LiDAR помогает замечать препятствия и корректировать путь."),
        ("Корпус и клиренс", "Конструкция уменьшает риск жёсткого контакта и доступа под платформу."),
        ("Оператор", "Человек может остановить миссию и взять управление."),
    ],
    "prototype_title": "Первый рабочий прототип",
    "prototype_sub": "На фотографии — реальная платформа проекта, а не визуализация.",
    "prototype_labels": [
        ("Mecanum-привод", "Четыре независимых колёсных модуля"),
        ("Электроника", "Pi, Mega, драйверы и питание"),
        ("Модульная рама", "Быстрый доступ для доработок"),
        ("Грузовая зона", "Проверка сценариев перевозки"),
    ],
    "expert_title": "Обратная связь авиационных специалистов",
    "expert_sub": "Команда представила проект представителям отрасли на форуме в Татарстане.",
    "expert_body": "Презентацию посетили представители аэропорта, специалисты по пассажирским перевозкам, пилоты, а также участники из Ульяновского авиационного института и МИРЭА.",
    "expert_result": "Общая оценка была положительной. Эксперты подтвердили актуальность задачи и выразили интерес к дальнейшим испытаниям.",
    "expert_truth": "Это подтверждает ценность идеи, но не означает готовность к сертифицированной эксплуатации.",
    "value_title": "Прототип развивается поэтапно",
    "value_sub": "Стоимость и модульность позволяют улучшать систему без полной пересборки.",
    "cost": "≈ 90 000 ₽",
    "cost_note": "Текущая стоимость экспериментальной платформы",
    "cost_body": "Шасси, моторы, колёса, драйверы, Raspberry Pi, Arduino, LiDAR, камера, экран, питание, проводка и материалы корпуса.",
    "improvements": [
        ("Зарядка", "Устранены проблемы, мешавшие стабильной подготовке к демонстрациям."),
        ("Корпус", "Усилена конструкция и улучшена защита компонентов."),
        ("Модульность", "Приводы, датчики и электронику можно заменять отдельно."),
    ],
    "roadmap_title": "Путь к испытаниям в аэропорту",
    "roadmap_sub": "Следующие шаги направлены на надёжность, восприятие среды и промышленную безопасность.",
    "roadmap": [
        ("01", "Промышленный привод", "Более долговечные колёса, моторы и драйверы."),
        ("02", "Дополнительные датчики", "Камеры и сенсоры для лучшего обзора и позиционирования."),
        ("03", "Новая логика движения", "Устойчивое поведение рядом с людьми и динамичными препятствиями."),
        ("04", "Интеграция", "Реальные данные рейсов, сервисные точки и процедуры аэропорта."),
        ("05", "Безопасный корпус", "Защита электроники, проверка зазоров и дальнейшая сертификация."),
    ],
    "closing": "Понятный маршрут через сложное пространство",
    "closing_body": "AirPorter объединяет информацию, сопровождение и помощь с багажом в одном мобильном сервисе.",
    "thanks": "Спасибо за внимание",
}

EN = {
    "cover_title": "A mobile robot assistant\nfor airports",
    "cover_sub": "Navigation · escort · luggage assistance",
    "cover_note": "Working engineering prototype\nRaspberry Pi 5 · Arduino Mega · ROS 2",
    "team": "Ilya Karyakin · Stanislav Paramonov · Artur Sabirzanov",
    "problem_title": "Why passengers need assistance",
    "problem_sub": "An airport is well organized as a system, yet it can be difficult for a person.",
    "problem_intro": "Large information flows, long walking routes, security procedures, and the search for the right zone create stress — especially for first-time visitors.",
    "problems": [
        ("Physical strain", "Passengers may need to move several bags across long terminal routes."),
        ("Navigation", "Check-in, security, service points, and the gate can be far apart."),
        ("Language barrier", "International passengers may struggle to get clear help quickly."),
    ],
    "solution_title": "One clear journey instead of many questions",
    "solution_sub": "AirPorter starts with the passenger’s need and turns it into a step-by-step service.",
    "solution_intro": "The robot combines a ticket workflow, information kiosk, route planning, and a mobile platform for carrying luggage.",
    "steps": [
        ("01", "Scan", "The ticket is read by camera, or its details are entered manually."),
        ("02", "Inform", "The screen shows the flight, time, gate, and available services."),
        ("03", "Choose assistance", "The passenger selects information, escort, or luggage help."),
        ("04", "Build a route", "The robot plans a path between preconfigured service points."),
    ],
    "modes_title": "Three operating scenarios",
    "modes_sub": "One interface provides a different level of assistance for each situation.",
    "modes": [
        ("Information only", "The robot shows flight data, the required zone, and the route. The session then ends."),
        ("Escort", "The passenger selects check-in, restroom, Duty Free, café, or gate. The robot plans a route and guides the person."),
        ("Luggage assistance", "The robot takes the bags and follows an agreed baggage workflow. Integration with real airport procedures is the next stage."),
    ],
    "hardware_title": "Hardware platform",
    "hardware_sub": "Two control levels separate interface and navigation from real-time drive control.",
    "hardware_note": "The real prototype is built on an 82 × 56 cm platform. Its open layout simplifies testing and upgrades.",
    "hardware": [
        ("Raspberry Pi 5 · 16 GB", "ROS 2 Jazzy, mapping, navigation, camera, kiosk, and admin panel."),
        ("Arduino Mega 2560", "Motors, encoders, watchdog, and safe stop."),
        ("4× Mecanum", "JGB37-520 + L298N: forward, reverse, lateral motion, and rotation."),
        ("COIN D6 · camera · display", "Obstacle map, ticket workflow, and passenger interaction."),
    ],
    "nav_title": "Navigation that accounts for robot size",
    "nav_sub": "The system already combines mapping, pose estimation, planning, and waypoint travel.",
    "nav_intro": "LiDAR scans the environment, encoders track motion, and the custom ROS 2 stack plans an A→B route around the 82 × 56 cm footprint.",
    "nav": [
        ("Map", "LiDAR measurements are filtered and added to an obstacle map."),
        ("Pose", "Odometry and scan matching estimate position and heading."),
        ("Plan", "A* searches for a route through free space."),
        ("Move", "The robot follows waypoints while retaining manual stop capability."),
    ],
    "ui_title": "An interface without unnecessary complexity",
    "ui_sub": "Large actions for the passenger and complete control for the operator.",
    "ui_flow": [
        ("1", "Choose language", "Russian · English · Tatar"),
        ("2", "Choose a service", "Check-in · gate · baggage · information"),
        ("3", "Scan the ticket", "Camera or manual input"),
        ("4", "Start assistance", "Information · route · escort"),
    ],
    "ui_cards": [
        ("Passenger kiosk", "Clear touch interface, ticket flow, destination selection, and route status."),
        ("Operator panel", "Health, map, STOP, mission, logs, and manual control for support and testing."),
    ],
    "safety_title": "Safety begins with stopping",
    "safety_sub": "For a service robot, predictable behavior matters more than maximum speed.",
    "safety": [
        ("Command timeout", "No valid command means the drive stops."),
        ("Kiosk heartbeat", "Loss of the active session cancels the escort."),
        ("Route control", "Movement is limited to the map and configured points."),
        ("Obstacle map", "LiDAR supports obstacle awareness and route correction."),
        ("Body and clearance", "The design reduces hard-contact and under-platform risks."),
        ("Human operator", "A person can stop the mission and take control."),
    ],
    "prototype_title": "The first working prototype",
    "prototype_sub": "The photograph shows the real project platform — not a render.",
    "prototype_labels": [
        ("Mecanum drive", "Four independent wheel modules"),
        ("Electronics", "Pi, Mega, drivers, and power"),
        ("Modular frame", "Fast access for modification"),
        ("Payload area", "Luggage-assistance testing"),
    ],
    "expert_title": "Feedback from aviation professionals",
    "expert_sub": "The team presented the project to industry representatives at a forum in Tatarstan.",
    "expert_body": "The audience included airport representatives, passenger-transport specialists, pilots, and participants from Ulyanovsk Aviation Institute and MIREA.",
    "expert_result": "The overall response was positive. Experts confirmed that the problem is relevant and expressed interest in further trials.",
    "expert_truth": "This validates the concept’s value, but it does not mean the robot is ready for certified operation.",
    "value_title": "The prototype develops step by step",
    "value_sub": "Its cost and modularity allow improvements without rebuilding the entire system.",
    "cost": "≈ 90,000 RUB",
    "cost_note": "Current experimental platform cost",
    "cost_body": "Chassis, motors, wheels, drivers, Raspberry Pi, Arduino, LiDAR, camera, display, power, wiring, and body materials.",
    "improvements": [
        ("Charging", "Issues that affected reliable preparation for demonstrations were corrected."),
        ("Body structure", "The frame was strengthened and component protection improved."),
        ("Modularity", "Drives, sensors, and electronics can be replaced independently."),
    ],
    "roadmap_title": "The path toward airport trials",
    "roadmap_sub": "Next steps focus on reliability, environment perception, and industrial safety.",
    "roadmap": [
        ("01", "Industrial drive", "More durable wheels, motors, and drivers."),
        ("02", "Additional sensing", "Cameras and sensors for wider awareness and stronger localization."),
        ("03", "New motion logic", "More robust behavior near people and dynamic obstacles."),
        ("04", "Integration", "Real flight data, service points, and airport procedures."),
        ("05", "Safe enclosure", "Protected electronics, tested clearances, and certification work."),
    ],
    "closing": "A clear journey through a complex space",
    "closing_body": "AirPorter combines information, guidance, and luggage assistance in one mobile service.",
    "thanks": "Thank you",
}


class Deck:
    def __init__(self, lang: str, data: dict, assets: dict[str, Path]) -> None:
        self.lang = lang
        self.data = data
        self.assets = assets
        self.app = win32.gencache.EnsureDispatch("PowerPoint.Application")
        self.app.Visible = TRUE
        self.pres = self.app.Presentations.Add()
        self.pres.PageSetup.SlideWidth = 960
        self.pres.PageSetup.SlideHeight = 540

    def slide(self, dark=False):
        s = self.pres.Slides.Add(self.pres.Slides.Count + 1, 12)
        s.FollowMasterBackground = FALSE
        s.Background.Fill.Solid()
        s.Background.Fill.ForeColor.RGB = NAVY if dark else PALE
        return s

    def rect(self, s, x, y, w, h, fill, line=None, radius=True):
        sh = s.Shapes.AddShape(5 if radius else 1, x, y, w, h)
        sh.Fill.Solid()
        sh.Fill.ForeColor.RGB = fill
        if line is None:
            sh.Line.Visible = FALSE
        else:
            sh.Line.Visible = TRUE
            sh.Line.ForeColor.RGB = line
            sh.Line.Weight = 1
        return sh

    def line(self, s, x1, y1, x2, y2, color=LINE, weight=1):
        sh = s.Shapes.AddLine(x1, y1, x2, y2)
        sh.Line.ForeColor.RGB = color
        sh.Line.Weight = weight
        return sh

    def circle(self, s, x, y, size, fill):
        return self.rect(s, x, y, size, size, fill)

    def text(self, s, x, y, w, h, value, size=14, bold=False, color=INK, align=1):
        sh = s.Shapes.AddTextbox(1, x, y, w, h)
        sh.TextFrame.WordWrap = TRUE
        sh.TextFrame.MarginLeft = 0
        sh.TextFrame.MarginRight = 0
        sh.TextFrame.MarginTop = 0
        sh.TextFrame.MarginBottom = 0
        tr = sh.TextFrame.TextRange
        tr.Text = value
        tr.Font.Name = "Arial"
        tr.Font.Size = size
        tr.Font.Bold = TRUE if bold else FALSE
        tr.Font.Color.RGB = color
        tr.ParagraphFormat.Alignment = align
        return sh

    def picture(self, s, path: Path, x, y, w, h, line=LINE):
        sh = s.Shapes.AddPicture(str(path), FALSE, TRUE, x, y, w, h)
        sh.Line.Visible = TRUE
        sh.Line.ForeColor.RGB = line
        sh.Line.Weight = 1
        return sh

    def header(self, s, section, title, subtitle=""):
        self.text(s, 48, 24, 300, 18, section.upper(), 9, True, BLUE)
        self.text(s, 48, 51, 850, 39, title, 27, True, INK)
        if subtitle:
            self.text(s, 48, 96, 850, 28, subtitle, 12, False, MUTED)
        self.line(s, 48, 135, 912, 135)

    def footer(self, s, label="AIRPORTER"):
        self.line(s, 48, 506, 912, 506)
        self.text(s, 48, 515, 420, 12, label, 8, True, MUTED)
        self.text(s, 842, 515, 70, 12, f"{s.SlideIndex:02d} / 13", 8, True, MUTED, 3)

    def card(self, s, x, y, w, h, title, body, accent=BLUE, number=None):
        self.rect(s, x, y, w, h, WHITE, LINE)
        self.rect(s, x, y, 5, h, accent, None, False)
        if number:
            self.text(s, x + 18, y + 16, 36, 18, number, 9, True, accent)
            title_y, body_y = y + 45, y + 83
        else:
            title_y, body_y = y + 20, y + 58
        self.text(s, x + 18, title_y, w - 36, 27, title, 15, True, INK)
        self.text(s, x + 18, body_y, w - 36, h - (body_y - y) - 18, body, 11, False, MUTED)

    def build(self) -> None:
        d = self.data

        # 1 — Cover
        s = self.slide(True)
        self.rect(s, 0, 0, 14, 540, BLUE, None, False)
        self.picture(s, self.assets["logo"], 52, 48, 250, 250, NAVY)
        self.text(s, 52, 315, 420, 72, d["cover_title"], 28, True, WHITE)
        self.text(s, 52, 399, 420, 28, d["cover_sub"], 13, False, rgb(198, 219, 233))
        self.picture(s, self.assets["wide"], 500, 48, 412, 256, rgb(104, 145, 172))
        self.rect(s, 500, 326, 412, 112, NAVY_SOFT, rgb(65, 99, 124))
        self.text(s, 522, 348, 365, 54, d["cover_note"], 13, False, WHITE)
        self.text(s, 52, 493, 700, 16, d["team"], 9, True, rgb(178, 204, 221))
        self.text(s, 842, 493, 70, 16, "01 / 13", 8, True, rgb(178, 204, 221), 3)

        # 2 — Problem
        s = self.slide()
        self.header(s, "02 · PROBLEM" if self.lang == "en" else "02 · ПРОБЛЕМА", d["problem_title"], d["problem_sub"])
        self.text(s, 48, 155, 864, 52, d["problem_intro"], 13, False, INK)
        x = 48
        for i, (title, body) in enumerate(d["problems"]):
            self.card(s, x, 230, 272, 230, title, body, [AMBER, BLUE, TEAL][i], f"0{i+1}")
            x += 296
        self.footer(s, "PASSENGER NEEDS")

        # 3 — Solution
        s = self.slide()
        self.header(s, "03 · SOLUTION" if self.lang == "en" else "03 · РЕШЕНИЕ", d["solution_title"], d["solution_sub"])
        self.text(s, 48, 154, 864, 45, d["solution_intro"], 13, False, INK)
        self.line(s, 100, 288, 860, 288, rgb(184, 210, 225), 2)
        x = 45
        for i, (n, title, body) in enumerate(d["steps"]):
            accent = TEAL if i == 3 else BLUE
            self.circle(s, x + 73, 248, 48, accent)
            self.text(s, x + 73, 263, 48, 18, n, 11, True, WHITE, 2)
            self.text(s, x, 322, 194, 30, title, 14, True, INK, 2)
            self.text(s, x + 8, 362, 178, 72, body, 10.5, False, MUTED, 2)
            x += 222
        self.rect(s, 160, 457, 640, 31, LIGHT_BLUE, None)
        self.text(s, 177, 465, 606, 15, "SCAN → INFORM → CHOOSE → ASSIST", 9, True, BLUE, 2)
        self.footer(s, "CLEAR SERVICE FLOW")

        # 4 — Modes
        s = self.slide()
        self.header(s, "04 · MODES" if self.lang == "en" else "04 · СЦЕНАРИИ", d["modes_title"], d["modes_sub"])
        x = 48
        accents = [BLUE, TEAL, AMBER]
        for i, (title, body) in enumerate(d["modes"]):
            self.rect(s, x, 170, 272, 285, [LIGHT_BLUE, LIGHT_TEAL, LIGHT_AMBER][i], None)
            self.circle(s, x + 20, 190, 36, accents[i])
            self.text(s, x + 20, 200, 36, 15, f"0{i+1}", 9, True, WHITE, 2)
            self.text(s, x + 20, 247, 232, 52, title, 17, True, INK)
            self.text(s, x + 20, 320, 232, 108, body, 11.5, False, MUTED)
            x += 296
        self.footer(s, "INFORMATION · ESCORT · LUGGAGE")

        # 5 — Hardware
        s = self.slide()
        self.header(s, "05 · HARDWARE" if self.lang == "en" else "05 · СИСТЕМА", d["hardware_title"], d["hardware_sub"])
        self.picture(s, self.assets["electronics"], 48, 160, 420, 250, LINE)
        self.text(s, 48, 427, 420, 48, d["hardware_note"], 10.5, False, MUTED)
        y = 157
        for i, (title, body) in enumerate(d["hardware"]):
            self.rect(s, 500, y, 412, 76, WHITE, LINE)
            self.circle(s, 518, y + 20, 30, [BLUE, TEAL, AMBER, NAVY_SOFT][i])
            self.text(s, 518, y + 28, 30, 12, str(i + 1), 8, True, WHITE, 2)
            self.text(s, 562, y + 12, 330, 20, title, 12, True, INK)
            self.text(s, 562, y + 38, 330, 28, body, 9.5, False, MUTED)
            y += 83
        self.footer(s, "REAL PROTOTYPE · 82 × 56 CM")

        # 6 — Navigation
        s = self.slide()
        self.header(s, "06 · NAVIGATION" if self.lang == "en" else "06 · НАВИГАЦИЯ", d["nav_title"], d["nav_sub"])
        self.text(s, 48, 154, 864, 52, d["nav_intro"], 13, False, INK)
        x = 48
        for i, (title, body) in enumerate(d["nav"]):
            self.rect(s, x, 232, 198, 212, WHITE, LINE)
            self.rect(s, x, 232, 198, 8, [BLUE, TEAL, AMBER, NAVY_SOFT][i], None, False)
            self.text(s, x + 18, 267, 162, 28, title, 15, True, INK)
            self.text(s, x + 18, 317, 162, 86, body, 10.5, False, MUTED)
            x += 222
        self.rect(s, 222, 463, 516, 28, LIGHT_BLUE, None)
        self.text(s, 240, 470, 480, 14, "LiDAR · ODOMETRY · A* · WAYPOINTS", 9, True, BLUE, 2)
        self.footer(s, "CUSTOM ROS 2 STACK")

        # 7 — Interface
        s = self.slide()
        self.header(s, "07 · INTERFACE" if self.lang == "en" else "07 · ИНТЕРФЕЙС", d["ui_title"], d["ui_sub"])
        self.rect(s, 48, 165, 520, 296, WHITE, LINE)
        y = 192
        for n, title, body in d["ui_flow"]:
            self.circle(s, 72, y, 34, BLUE if n != "4" else TEAL)
            self.text(s, 72, y + 9, 34, 14, n, 9, True, WHITE, 2)
            self.text(s, 125, y + 1, 185, 20, title, 12, True, INK)
            self.text(s, 316, y + 1, 225, 27, body, 9.5, False, MUTED)
            y += 59
        self.card(s, 600, 165, 312, 132, d["ui_cards"][0][0], d["ui_cards"][0][1], BLUE)
        self.card(s, 600, 329, 312, 132, d["ui_cards"][1][0], d["ui_cards"][1][1], TEAL)
        self.footer(s, "PASSENGER + OPERATOR")

        # 8 — Safety
        s = self.slide()
        self.header(s, "08 · SAFETY" if self.lang == "en" else "08 · БЕЗОПАСНОСТЬ", d["safety_title"], d["safety_sub"])
        for i, (title, body) in enumerate(d["safety"]):
            col, row = i % 3, i // 3
            x, y = 48 + col * 296, 165 + row * 146
            self.rect(s, x, y, 272, 126, WHITE, LINE)
            self.circle(s, x + 18, y + 18, 28, TEAL if i < 2 else BLUE)
            self.text(s, x + 18, y + 25, 28, 12, "✓", 9, True, WHITE, 2)
            self.text(s, x + 58, y + 18, 190, 22, title, 12, True, INK)
            self.text(s, x + 18, y + 57, 230, 50, body, 9.5, False, MUTED)
        self.rect(s, 160, 465, 640, 27, LIGHT_AMBER, None)
        note = "Prototype safety requires further testing and certification." if self.lang == "en" else "Безопасность прототипа требует дальнейших испытаний и сертификации."
        self.text(s, 178, 472, 604, 13, note, 9, True, rgb(143, 94, 28), 2)
        self.footer(s, "STOP FIRST · HUMAN OVERRIDE")

        # 9 — Prototype
        s = self.slide()
        self.header(s, "09 · PROTOTYPE" if self.lang == "en" else "09 · ПРОТОТИП", d["prototype_title"], d["prototype_sub"])
        self.picture(s, self.assets["wide"], 48, 158, 618, 322, LINE)
        y = 158
        for i, (title, body) in enumerate(d["prototype_labels"]):
            self.rect(s, 694, y, 218, 72, WHITE, LINE)
            self.text(s, 712, y + 12, 180, 20, title, 11, True, INK)
            self.text(s, 712, y + 38, 180, 23, body, 9, False, MUTED)
            y += 82
        self.footer(s, "ACTUAL PROJECT PHOTO")

        # 10 — Expert feedback
        s = self.slide()
        self.header(s, "10 · FEEDBACK" if self.lang == "en" else "10 · ОЦЕНКА", d["expert_title"], d["expert_sub"])
        self.rect(s, 48, 168, 548, 268, WHITE, LINE)
        self.text(s, 72, 194, 500, 92, d["expert_body"], 13, False, INK)
        self.line(s, 72, 309, 572, 309)
        self.text(s, 72, 331, 500, 78, d["expert_result"], 13, True, NAVY_SOFT)
        self.rect(s, 628, 168, 284, 268, LIGHT_BLUE, None)
        label = "ACCURATE CONCLUSION" if self.lang == "en" else "ТОЧНЫЙ ВЫВОД"
        self.text(s, 654, 194, 232, 20, label, 9, True, BLUE)
        self.text(s, 654, 242, 232, 135, d["expert_truth"], 15, True, INK)
        self.footer(s, "INDUSTRY INTEREST · NEXT STEP: TRIALS")

        # 11 — Value and improvements
        s = self.slide()
        self.header(s, "11 · VALUE" if self.lang == "en" else "11 · ЭКОНОМИКА", d["value_title"], d["value_sub"])
        self.rect(s, 48, 166, 356, 290, NAVY, None)
        self.text(s, 74, 195, 306, 48, d["cost"], 31, True, WHITE)
        self.text(s, 74, 253, 306, 32, d["cost_note"], 10, True, rgb(189, 214, 230))
        self.line(s, 74, 307, 378, 307, rgb(68, 99, 123))
        self.text(s, 74, 331, 306, 88, d["cost_body"], 11, False, rgb(218, 232, 241))
        y = 166
        for i, (title, body) in enumerate(d["improvements"]):
            accent = [TEAL, BLUE, AMBER][i]
            self.rect(s, 440, y, 472, 82, WHITE, LINE)
            self.rect(s, 440, y, 5, 82, accent, None, False)
            self.circle(s, 460, y + 23, 30, accent)
            self.text(s, 460, y + 31, 30, 12, str(i + 1), 8, True, WHITE, 2)
            self.text(s, 508, y + 13, 380, 21, title, 12, True, INK)
            self.text(s, 508, y + 40, 380, 29, body, 9.5, False, MUTED)
            y += 100
        self.footer(s, "MODULAR · REPAIRABLE · UPGRADABLE")

        # 12 — Roadmap
        s = self.slide()
        self.header(s, "12 · ROADMAP" if self.lang == "en" else "12 · ПЛАНЫ", d["roadmap_title"], d["roadmap_sub"])
        y = 159
        for i, (n, title, body) in enumerate(d["roadmap"]):
            self.circle(s, 56, y + 3, 34, TEAL if i == 4 else BLUE)
            self.text(s, 56, y + 12, 34, 13, n, 8, True, WHITE, 2)
            self.text(s, 112, y, 222, 23, title, 12, True, INK)
            self.text(s, 354, y, 530, 31, body, 10.5, False, MUTED)
            if i < 4:
                self.line(s, 73, y + 39, 73, y + 58, LINE, 2)
            y += 65
        self.rect(s, 190, 466, 580, 27, LIGHT_TEAL, None)
        target = "Goal: controlled airport trials and evidence-based refinement." if self.lang == "en" else "Цель: контролируемые испытания в аэропорту и доработка по результатам."
        self.text(s, 208, 473, 544, 13, target, 9, True, rgb(43, 116, 115), 2)
        self.footer(s, "BUILD → TEST → MEASURE → IMPROVE")

        # 13 — Closing
        s = self.slide(True)
        self.picture(s, self.assets["logo"], 355, 35, 250, 250, NAVY)
        self.text(s, 115, 310, 730, 52, d["closing"], 25, True, WHITE, 2)
        self.text(s, 155, 378, 650, 56, d["closing_body"], 14, False, rgb(198, 219, 233), 2)
        self.rect(s, 333, 458, 294, 38, NAVY_SOFT, rgb(65, 99, 124))
        self.text(s, 333, 469, 294, 17, d["thanks"], 11, True, WHITE, 2)
        self.text(s, 48, 515, 420, 12, "AIRPORTER TEAM · 2026", 8, True, rgb(178, 204, 221))
        self.text(s, 842, 515, 70, 12, "13 / 13", 8, True, rgb(178, 204, 221), 3)

    def save_pdf(self, output: Path) -> None:
        self.build()
        temp_pptx = Path(tempfile.gettempdir()) / f"airporter_{self.lang}_calm.pptx"
        temp_pptx.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        self.pres.SaveAs(str(temp_pptx))
        self.pres.SaveAs(str(output), 32)
        self.pres.Close()
        self.app.Quit()
        temp_pptx.unlink(missing_ok=True)


def prepare_assets(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)

    logo = Image.open(SOURCE_LOGO).convert("RGBA")
    pixels = logo.load()
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, a = pixels[x, y]
            if max(r, g, b) < 28:
                pixels[x, y] = (r, g, b, 0)
    logo_box = logo.getbbox()
    if logo_box:
        logo = logo.crop(logo_box)
    logo_out = directory / "logo_transparent.png"
    logo.save(logo_out)

    photo = Image.open(SOURCE_PHOTO).convert("RGB")
    photo = ImageEnhance.Contrast(photo).enhance(1.04)
    wide = ImageOps.fit(photo, (1400, 820), method=Image.Resampling.LANCZOS, centering=(0.5, 0.48))
    electronics = ImageOps.fit(photo, (1000, 600), method=Image.Resampling.LANCZOS, centering=(0.55, 0.52))
    wide_out = directory / "prototype_wide.jpg"
    electronics_out = directory / "prototype_electronics.jpg"
    wide.save(wide_out, quality=94)
    electronics.save(electronics_out, quality=94)
    return {"logo": logo_out, "wide": wide_out, "electronics": electronics_out}


def main() -> None:
    if not SOURCE_LOGO.is_file() or not SOURCE_PHOTO.is_file():
        raise FileNotFoundError("AirPorter source materials are missing")
    temp = Path(tempfile.gettempdir()) / "airporter_calm_assets"
    shutil.rmtree(temp, ignore_errors=True)
    assets = prepare_assets(temp)
    Deck("ru", RU, assets).save_pdf(OUT_RU)
    Deck("en", EN, assets).save_pdf(OUT_EN)
    shutil.rmtree(temp, ignore_errors=True)
    print(OUT_RU)
    print(OUT_EN)


if __name__ == "__main__":
    main()
