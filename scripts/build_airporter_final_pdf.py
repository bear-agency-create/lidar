# -*- coding: utf-8 -*-
"""Build the final material-driven AirPorter English PDF."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance
import win32com.client as win32

DESKTOP = Path.home() / "Desktop"
MATERIALS = DESKTOP / "материал для AirPorter"
LOGO = MATERIALS / "AIRPORTER_logo.png"
ROBOT = MATERIALS / "photo_2026-08-07_13-37-15.jpg"
OUTPUT = DESKTOP / "AirPorter — Final English Presentation.pdf"


def rgb(r: int, g: int, b: int) -> int:
    return r + (g << 8) + (b << 16)


NAVY = rgb(7, 31, 57)
NAVY_2 = rgb(11, 49, 82)
BLUE = rgb(18, 151, 238)
CYAN = rgb(39, 205, 230)
GREEN = rgb(31, 193, 128)
AMBER = rgb(255, 175, 45)
RED = rgb(231, 79, 91)
INK = rgb(17, 42, 67)
MUTED = rgb(102, 126, 148)
PALE = rgb(242, 247, 251)
WHITE = rgb(255, 255, 255)
LINE = rgb(215, 228, 238)
TRUE, FALSE = -1, 0


class Deck:
    def __init__(self) -> None:
        self.app = win32.gencache.EnsureDispatch("PowerPoint.Application")
        self.app.Visible = TRUE
        self.pres = self.app.Presentations.Add()
        self.pres.PageSetup.SlideWidth = 960
        self.pres.PageSetup.SlideHeight = 540

    def slide(self, dark: bool = False):
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
            sh.Line.ForeColor.RGB = line
            sh.Line.Weight = 1
        return sh

    def line(self, s, x1, y1, x2, y2, color, weight=1.5):
        sh = s.Shapes.AddLine(x1, y1, x2, y2)
        sh.Line.ForeColor.RGB = color
        sh.Line.Weight = weight
        return sh

    def circle(self, s, x, y, size, fill, line=None):
        return self.rect(s, x, y, size, size, fill, line, radius=True)

    def text(
        self, s, x, y, w, h, value, size=14, bold=False,
        color=INK, align=1, font="Arial"
    ):
        sh = s.Shapes.AddTextbox(1, x, y, w, h)
        sh.TextFrame.WordWrap = TRUE
        sh.TextFrame.MarginLeft = 0
        sh.TextFrame.MarginRight = 0
        sh.TextFrame.MarginTop = 0
        sh.TextFrame.MarginBottom = 0
        tr = sh.TextFrame.TextRange
        tr.Text = value
        tr.Font.Name = font
        tr.Font.Size = size
        tr.Font.Bold = TRUE if bold else FALSE
        tr.Font.Color.RGB = color
        tr.ParagraphFormat.Alignment = align
        return sh

    def picture(self, s, path: Path, x, y, w, h, line=BLUE):
        sh = s.Shapes.AddPicture(str(path), FALSE, TRUE, x, y, w, h)
        sh.Line.Visible = TRUE
        sh.Line.ForeColor.RGB = line
        sh.Line.Weight = 1.4
        return sh

    def header(self, s, section, title, subtitle="", dark=False):
        fg = WHITE if dark else INK
        self.text(s, 44, 25, 280, 18, section.upper(), 10, True, CYAN if dark else BLUE)
        self.text(s, 44, 51, 850, 42, title, 30, True, fg)
        if subtitle:
            self.text(s, 44, 98, 850, 28, subtitle, 14, False, rgb(185, 213, 232) if dark else MUTED)
        self.line(s, 44, 132, 916, 132, rgb(45, 83, 112) if dark else LINE, 1)

    def footer(self, s, label, dark=False):
        color = rgb(169, 200, 221) if dark else MUTED
        self.line(s, 44, 505, 916, 505, rgb(45, 83, 112) if dark else LINE, 1)
        self.text(s, 44, 514, 650, 14, label, 9, True, color)
        self.text(s, 850, 514, 66, 14, f"{s.SlideIndex:02d} / 13", 9, True, color, 3)

    def card(self, s, x, y, w, h, title, body, accent=BLUE, dark=False, number=None):
        fill = NAVY_2 if dark else WHITE
        self.rect(s, x, y, w, h, fill, rgb(37, 81, 113) if dark else LINE)
        self.rect(s, x, y, 6, h, accent, None, radius=False)
        if number:
            self.text(s, x + 18, y + 14, 40, 18, number, 9, True, accent)
        self.text(s, x + 18, y + (38 if number else 18), w - 36, 30, title, 16, True, WHITE if dark else INK)
        self.text(s, x + 18, y + (76 if number else 58), w - 36, h - (88 if number else 70), body, 12, False, rgb(185, 213, 232) if dark else MUTED)

    def save_pdf(self, output: Path):
        temp_pptx = Path(tempfile.gettempdir()) / "airporter_final_build.pptx"
        if temp_pptx.exists():
            temp_pptx.unlink()
        if output.exists():
            output.unlink()
        self.pres.SaveAs(str(temp_pptx))
        self.pres.SaveAs(str(output), 32)
        self.pres.Close()
        self.app.Quit()
        temp_pptx.unlink(missing_ok=True)


def make_crops(temp: Path) -> dict[str, Path]:
    temp.mkdir(parents=True, exist_ok=True)
    image = Image.open(ROBOT).convert("RGB")
    image = ImageEnhance.Contrast(image).enhance(1.05)
    crops = {
        "wide": (0, 0, image.width, image.height),
        "electronics": (340, 120, 1300, 620),
        "drive": (0, 30, 720, 650),
        "frame": (780, 0, 1750, 650),
    }
    result = {}
    for name, box in crops.items():
        out = temp / f"{name}.jpg"
        image.crop(box).save(out, quality=94)
        result[name] = out
    return result


def build() -> None:
    if not LOGO.is_file() or not ROBOT.is_file():
        raise FileNotFoundError("AirPorter logo or prototype photo is missing")

    temp = Path(tempfile.gettempdir()) / "airporter_final_assets"
    if temp.exists():
        shutil.rmtree(temp)
    crops = make_crops(temp)
    d = Deck()

    # 1 — Introduction
    s = d.slide(True)
    d.rect(s, 0, 0, 16, 540, CYAN, None, False)
    d.picture(s, LOGO, 42, 42, 300, 300, NAVY)
    d.text(s, 52, 344, 430, 56, "MOBILE ROBOT ASSISTANT\nFOR AIRPORTS", 26, True, WHITE)
    d.text(
        s, 52, 400, 420, 63,
        "Designed to reduce passenger stress, simplify navigation, "
        "and remove part of the physical burden of carrying luggage.",
        15, False, rgb(190, 218, 236)
    )
    d.picture(s, crops["wide"], 505, 54, 410, 244, CYAN)
    d.rect(s, 505, 318, 410, 134, NAVY_2, rgb(37, 81, 113))
    d.text(s, 525, 337, 365, 19, "WORKING ENGINEERING PROTOTYPE", 11, True, CYAN)
    d.text(s, 525, 371, 365, 52, "Raspberry Pi 5 · Arduino Mega 2560\nROS 2 Jazzy · COIN D6 LiDAR · Mecanum drive", 14, False, WHITE)
    d.text(s, 52, 493, 740, 18, "Ilya Karyakin · Stanislav Paramonov · Artur Sabirzanov", 11, True, rgb(161, 196, 218))
    d.text(s, 840, 493, 75, 18, "01 / 13", 9, True, rgb(161, 196, 218), 3)

    # 2 — Problem
    s = d.slide()
    d.header(s, "02 · Problem", "Why passengers need assistance",
             "A modern airport is coordinated — but from a passenger’s perspective it can be overwhelming.")
    d.text(
        s, 44, 151, 872, 48,
        "Flight information, service points, security procedures, and long walking routes are spread across "
        "a large terminal. Visitors — especially those unfamiliar with the airport — must process all of this "
        "under time pressure.",
        12.5, False, INK
    )
    d.card(s, 44, 222, 272, 240, "Physical load",
           "Passengers may carry several bags over long distances. This is tiring for families, older people, "
           "and travelers with reduced mobility.", AMBER, number="01")
    d.card(s, 344, 222, 272, 240, "Navigation",
           "Finding check-in, security, baggage claim, service points, and the correct gate can take time and "
           "create a risk of missing a flight.", BLUE, number="02")
    d.card(s, 644, 222, 272, 240, "Language barrier",
           "International passengers may struggle to understand signs, announcements, and instructions or to "
           "ask airport staff for help.", GREEN, number="03")
    d.footer(s, "THE PROBLEM IS NOT A LACK OF INFORMATION — IT IS ACCESS TO IT")

    # 3 — Solution
    s = d.slide(True)
    d.header(s, "03 · Solution", "One service, adapted to the passenger", dark=True)
    d.text(
        s, 44, 151, 872, 52,
        "AirPorter combines a passenger kiosk, ticket interaction, route planning, and a mobile luggage platform. "
        "The robot starts with the passenger’s needs and turns them into a clear step-by-step journey.",
        12.5, False, rgb(210, 232, 245)
    )
    steps = [
        ("01", "SCAN", "The passenger scans a ticket or enters the details manually."),
        ("02", "INFORM", "The screen shows flight, gate, time, and relevant airport services."),
        ("03", "CHOOSE", "The passenger selects information, escort, or luggage assistance."),
        ("04", "ROUTE", "The robot plans the required route between configured service points."),
    ]
    x = 44
    for n, title, body in steps:
        d.card(s, x, 230, 202, 196, title, body, CYAN if n != "03" else GREEN, True, n)
        x += 223
    d.rect(s, 44, 448, 872, 38, NAVY_2, rgb(37, 81, 113))
    d.text(s, 60, 458, 840, 18, "RESULT: less uncertainty for the passenger and fewer routine questions for staff.", 11, True, WHITE, 2)
    d.footer(s, "SCAN → INFORM → CHOOSE → ASSIST", True)

    # 4 — System
    s = d.slide()
    d.header(s, "04 · Robot system", "The hardware behind the prototype",
             "Two control levels separate navigation and interface logic from real-time motor control.")
    d.picture(s, crops["electronics"], 44, 158, 440, 260, BLUE)
    d.text(s, 44, 433, 440, 44, "Real prototype platform: 82 × 56 cm. The open layout provides direct access for testing and modification.", 10.5, False, MUTED)
    specs = [
        ("MAIN COMPUTER", "Raspberry Pi 5 · 16 GB", "ROS 2 Jazzy, LiDAR mapping, route planning, camera, kiosk, and admin panel."),
        ("MOTION CONTROL", "Arduino Mega 2560", "Motor commands, encoder reading, watchdog, and safe stop."),
        ("DRIVE", "4× JGB37-520 + L298N", "Four Mecanum wheels enable forward, reverse, lateral motion, and rotation."),
        ("SENSORS & UI", "COIN D6 · camera · 10.1″ display", "Environment scanning, ticket interaction, and passenger interface."),
    ]
    y = 153
    accents = [BLUE, CYAN, GREEN, AMBER]
    for i, (tag, title, body) in enumerate(specs):
        d.rect(s, 515, y, 401, 77, WHITE, LINE)
        d.text(s, 533, y + 11, 120, 14, tag, 8, True, accents[i])
        d.text(s, 660, y + 9, 238, 21, title, 12, True, INK)
        d.text(s, 533, y + 37, 365, 30, body, 9.5, False, MUTED)
        y += 84
    d.footer(s, "REAL COMPONENTS · MODULAR ARCHITECTURE · SERVICEABLE PROTOTYPE")

    # 5 — Navigation
    s = d.slide(True)
    d.header(s, "05 · Navigation", "The robot understands its size and direction",
             "The current software already combines mapping, pose estimation, path planning, and route following.", True)
    d.text(
        s, 44, 151, 872, 54,
        "COIN D6 LiDAR scans the environment while encoder odometry tracks motion. The robot builds an occupancy "
        "map, estimates its pose, plans an A→B path, and follows waypoints while accounting for its 82 × 56 cm footprint.",
        12, False, rgb(210, 232, 245)
    )
    nav = [
        ("MAP", "LiDAR measurements are filtered and integrated into a live obstacle map."),
        ("POSE", "Odometry and scan matching estimate position and heading."),
        ("PLAN", "A* searches for an efficient route around occupied areas."),
        ("MOVE", "A route follower converts waypoints into safe drive commands."),
    ]
    x = 44
    for i, (title, body) in enumerate(nav):
        d.card(s, x, 236, 202, 190, title, body, [CYAN, BLUE, GREEN, AMBER][i], True, f"0{i+1}")
        x += 223
    d.rect(s, 44, 448, 872, 38, NAVY_2, rgb(37, 81, 113))
    d.text(s, 60, 458, 840, 18, "Custom ROS 2 stack: occupancy grid · A* · route following · operator control", 10.5, True, WHITE, 2)
    d.footer(s, "SOFTWARE EXISTS; REAL-TERMINAL VALIDATION REMAINS THE NEXT STEP", True)

    # 6 — Interface
    s = d.slide()
    d.header(s, "06 · Passenger interface", "Designed to be understood at a glance",
             "The screen groups airport services into large, clear actions and supports three languages.")
    d.rect(s, 44, 162, 515, 300, WHITE, LINE)
    d.text(s, 66, 181, 470, 20, "PASSENGER FLOW", 9, True, BLUE)
    flow = [
        ("1", "Choose language", "Russian · English · Tatar"),
        ("2", "Select a service", "Check-in · gate · baggage claim · information"),
        ("3", "Scan the ticket", "Camera scan or manual input"),
        ("4", "Start assistance", "Information, route guidance, or escort"),
    ]
    y = 218
    for n, title, body in flow:
        d.circle(s, 68, y, 34, BLUE if n != "4" else GREEN)
        d.text(s, 68, y + 8, 34, 15, n, 10, True, WHITE, 2)
        d.text(s, 119, y - 1, 190, 21, title, 12, True, INK)
        d.text(s, 315, y, 215, 28, body, 9.5, False, MUTED)
        y += 56
    d.card(s, 590, 162, 326, 138, "Passenger kiosk",
           "Touch-first controls, ticket workflow, destination selection, route status, and large interface elements.", BLUE)
    d.card(s, 590, 324, 326, 138, "Operator panel",
           "System health, map, emergency STOP, mission status, logs, and manual control for testing and support.", GREEN)
    d.footer(s, "PASSENGER-FACING SIMPLICITY · OPERATOR-FACING CONTROL")

    # 7 — Safety
    s = d.slide(True)
    d.header(s, "07 · Safety", "A service robot must fail safely",
             "Predictable stopping and operator control are more important than maximum speed around passengers.", True)
    safety = [
        ("COMMAND TIMEOUT", "If valid motion commands stop arriving, the drive layer stops the robot."),
        ("KIOSK HEARTBEAT", "Loss of the active kiosk session cancels the escort and requests a stop."),
        ("ROUTE CONTROL", "Movement is limited to mapped routes and configured service points."),
        ("OBSTACLE MAP", "LiDAR supports obstacle awareness and route correction."),
        ("BODY & CLEARANCE", "The body is designed to reduce impact severity and limit access beneath the platform."),
        ("HUMAN OVERRIDE", "An operator can stop a mission and take manual control at any time."),
    ]
    for i, (title, body) in enumerate(safety):
        col, row = i % 3, i // 3
        x, y = 44 + col * 297, 165 + row * 145
        d.card(s, x, y, 277, 124, title, body, GREEN if i < 2 else CYAN, True)
    d.rect(s, 44, 463, 872, 26, NAVY_2, rgb(37, 81, 113))
    d.text(s, 60, 469, 840, 14, "Engineering prototype — certification and full airport safety validation are future work.", 9.5, True, rgb(210, 232, 245), 2)
    d.footer(s, "STOP FIRST · MONITOR CONNECTION · KEEP A HUMAN IN CONTROL", True)

    # 8 — Prototype photo
    s = d.slide()
    d.header(s, "08 · First prototype", "A real platform built for experimentation",
             "The photograph shows the actual robot used to integrate mechanics, electronics, control, and software.")
    d.picture(s, crops["wide"], 44, 153, 620, 323, BLUE)
    callouts = [
        ("01", "Mecanum drive", "Four independent wheel modules"),
        ("02", "Control electronics", "Pi, Mega, drivers, power conversion"),
        ("03", "Modular frame", "Accessible layout for fast iteration"),
        ("04", "Payload area", "Platform for luggage-assistance tests"),
    ]
    y = 153
    for n, title, body in callouts:
        d.rect(s, 690, y, 226, 72, WHITE, LINE)
        d.text(s, 705, y + 12, 28, 18, n, 9, True, BLUE)
        d.text(s, 744, y + 9, 155, 20, title, 11, True, INK)
        d.text(s, 705, y + 36, 194, 24, body, 9, False, MUTED)
        y += 81
    d.footer(s, "ACTUAL PROJECT PHOTO · NOT A STOCK RENDER")

    # 9 — Expert assessment
    s = d.slide(True)
    d.header(s, "09 · Expert assessment", "Feedback from aviation professionals",
             "The team presented the project at a Tatarstan forum attended by representatives of the aviation sector.", True)
    d.text(
        s, 44, 153, 560, 105,
        "During the final day, AirPorter was presented to airport management representatives, passenger-transport "
        "specialists, pilots, and delegates from Ulyanovsk Aviation Institute and MIREA.",
        13, False, rgb(210, 232, 245)
    )
    d.text(
        s, 44, 278, 560, 116,
        "The overall response was positive. Experts highlighted the practical value of navigation and luggage "
        "assistance and expressed interest in further testing. This validates the problem and the concept — "
        "not yet full operational readiness.",
        13, False, rgb(210, 232, 245)
    )
    d.rect(s, 640, 153, 276, 241, NAVY_2, CYAN)
    d.text(s, 668, 180, 220, 26, "WHAT THE FEEDBACK MEANS", 10, True, CYAN)
    d.text(s, 668, 229, 220, 119, "✓ Relevant airport problem\n\n✓ Understandable service model\n\n✓ Worth further trials\n\n→ Terminal validation is still required", 12, False, WHITE)
    d.rect(s, 44, 427, 872, 57, NAVY_2, rgb(37, 81, 113))
    d.text(s, 64, 441, 832, 30, "Our claim is careful: the project has industry interest and a path to testing; it is not a certified deployed product.", 10.5, True, WHITE, 2)
    d.footer(s, "POSITIVE FEEDBACK · HONEST STATUS · NEXT STEP: FIELD TESTS", True)

    # 10 — Improvements
    s = d.slide()
    d.header(s, "10 · Improvements", "The prototype continues to evolve",
             "After the first demonstrations, the team identified practical weaknesses and began improving them.")
    d.picture(s, crops["frame"], 44, 158, 410, 260, BLUE)
    d.text(s, 44, 433, 410, 45, "Current frame and drive area. The architecture remains open and modular so that each subsystem can be upgraded separately.", 10.5, False, MUTED)
    d.card(s, 488, 158, 428, 120, "Charging system",
           "The team corrected charging-related issues to make preparation and repeated demonstrations more reliable.", GREEN, number="01")
    d.card(s, 488, 298, 428, 120, "Body structure",
           "The enclosure and frame were improved to protect components, support the payload, and move toward a safer service-robot form.", BLUE, number="02")
    d.rect(s, 488, 438, 428, 40, WHITE, LINE)
    d.text(s, 505, 449, 394, 17, "Iterative engineering: test → identify → improve → retest", 10.5, True, INK, 2)
    d.footer(s, "CHANGES ARE PRIORITIZED BY SAFETY, RELIABILITY, TIME, AND BUDGET")

    # 11 — Economics
    s = d.slide(True)
    d.header(s, "11 · Economics", "A functional prototype for about 90,000 RUB",
             "The estimate covers the current experimental platform rather than a certified industrial product.", True)
    d.text(s, 44, 162, 380, 58, "90,000", 42, True, CYAN)
    d.text(s, 44, 224, 380, 30, "RUSSIAN RUBLES · CURRENT PROTOTYPE", 10, True, rgb(190, 218, 236))
    d.text(
        s, 44, 281, 380, 126,
        "The budget includes the chassis, four motors, Mecanum wheels, motor drivers, Arduino Mega, Raspberry Pi 5, "
        "LiDAR, camera, display, power electronics, wiring, and body materials.",
        13, False, WHITE
    )
    d.rect(s, 468, 160, 448, 274, NAVY_2, rgb(37, 81, 113))
    d.text(s, 494, 185, 395, 24, "WHY THE MODULAR APPROACH MATTERS", 11, True, GREEN)
    d.text(s, 494, 231, 395, 155,
           "• Components can be replaced independently.\n\n"
           "• New sensors do not require rebuilding the entire robot.\n\n"
           "• Testing can continue while individual modules evolve.\n\n"
           "• Industrial upgrades can be introduced step by step.",
           12, False, rgb(210, 232, 245))
    d.footer(s, "PROTOTYPE COST ≠ PRODUCTION PRICE", True)

    # 12 — Future
    s = d.slide()
    d.header(s, "12 · Roadmap", "From a prototype to an airport-ready system",
             "The team plans to improve mobility, perception, integration, and industrial safety.")
    roadmap = [
        ("01", "Industrial mobility", "More durable wheels, motors, and drivers for long-term operation."),
        ("02", "Richer perception", "Additional cameras and sensors for wider awareness and better localization."),
        ("03", "Navigation logic", "More robust behavior around people and changing obstacles."),
        ("04", "Airport integration", "Connection to real flight data, service points, and operating procedures."),
        ("05", "Safe enclosure", "Industrial body, protected electronics, tested clearances, and certification work."),
    ]
    y = 156
    for i, (n, title, body) in enumerate(roadmap):
        accent = GREEN if i == 4 else BLUE
        d.circle(s, 52, y + 2, 34, accent)
        d.text(s, 52, y + 10, 34, 15, n, 9, True, WHITE, 2)
        d.text(s, 108, y, 220, 23, title, 12.5, True, INK)
        d.text(s, 344, y, 542, 35, body, 10.5, False, MUTED)
        if i < 4:
            d.line(s, 69, y + 38, 69, y + 61, LINE, 2)
        y += 66
    d.rect(s, 44, 455, 872, 33, WHITE, LINE)
    d.text(s, 60, 464, 840, 16, "Target: field trials in a controlled airport environment, followed by evidence-based refinement.", 10, True, INK, 2)
    d.footer(s, "MECHANICS → PERCEPTION → NAVIGATION → INTEGRATION → VALIDATION")

    # 13 — Closing
    s = d.slide(True)
    d.picture(s, LOGO, 330, 25, 300, 300, NAVY)
    d.text(s, 105, 326, 750, 36, "A CLEARER JOURNEY THROUGH THE AIRPORT", 22, True, WHITE, 2)
    d.text(
        s, 145, 378, 670, 64,
        "AirPorter brings information, guidance, and luggage assistance into one mobile service — "
        "with a real prototype and a realistic path toward further testing.",
        13, False, rgb(190, 218, 236), 2
    )
    d.rect(s, 325, 462, 310, 42, NAVY_2, CYAN)
    d.text(s, 325, 474, 310, 18, "THANK YOU · QUESTIONS?", 11, True, WHITE, 2)
    d.text(s, 44, 517, 650, 14, "AIRPORTER TEAM · 2026", 8, True, rgb(161, 196, 218))
    d.text(s, 850, 517, 66, 14, "13 / 13", 8, True, rgb(161, 196, 218), 3)

    d.save_pdf(OUTPUT)
    shutil.rmtree(temp, ignore_errors=True)
    print(OUTPUT)


if __name__ == "__main__":
    build()
