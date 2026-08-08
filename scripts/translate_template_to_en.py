# -*- coding: utf-8 -*-
"""Translate the provided AeroPorter template to English, preserving its design."""
from __future__ import annotations

from pathlib import Path

import win32com.client as win32
from win32com.client import constants as c

SOURCE = Path(r"C:\Users\user\Downloads\Telegram Desktop\AeroPorter_презентация (2).pptx")
DEST = Path(r"C:\Users\user\Desktop\AeroPorter English — original design.pptx")
PDF = Path(r"C:\Users\user\Desktop\AeroPorter English — original design.pdf")


TEXT: dict[tuple[int, int], str] = {
    # Slide 1
    (1, 2): "ROBOTICS · PROJECT WORK",
    (1, 3): "AeroPorter",
    (1, 4): "Mobile robot assistant\rfor airports",
    (1, 5): "Goal: scan a ticket · show flight data · build an escort route",
    (1, 7): "Team",
    (1, 8): "Ilya Karyakin · Grade 9\rStanislav Paramonov · Grade 9\rArtur Sabirzanov · Grade 11",
    (1, 9): "Supervisor",
    (1, 10): "Alexander Borisovich\rChetvergov",
    # Slide 2
    (2, 2): "01 · THE PROBLEM",
    (2, 3): "Airports are difficult for passengers",
    (2, 4): "Information changes quickly, while help is needed here and now",
    (2, 10): "Navigation",
    (2, 11): "Finding check-in, the gate, and baggage claim takes time.",
    (2, 17): "Information",
    (2, 18): "Flight status and gate number can change.",
    (2, 25): "Accessibility",
    (2, 26): "Language, age, and stress make communication harder.",
    # Slide 3
    (3, 2): "02 · THE SOLUTION",
    (3, 3): "One clear journey: from ticket to destination",
    (3, 11): "Scanning",
    (3, 12): "The camera reads the ticket barcode",
    (3, 20): "Information",
    (3, 21): "The screen shows flight, time, and gate",
    (3, 28): "Route",
    (3, 29): "Ticket data is linked to a configured destination",
    (3, 36): "Escort",
    (3, 37): "The robot starts an A→B route",
    (3, 39): "Goal: reduce passenger stress and staff workload",
    # Slide 4
    (4, 2): "03 · PROTOTYPE",
    (4, 3): "Hardware platform",
    (4, 4): "Agile chassis and two levels of control",
    (4, 8): "Raspberry Pi 5",
    (4, 9): "image processing, ROS 2, and interface",
    (4, 13): "Arduino Mega",
    (4, 14): "motor control, encoders, command watchdog",
    (4, 18): "4 Mecanum wheels",
    (4, 19): "forward, lateral, and rotational motion",
    (4, 23): "Drive and sensors",
    (4, 24): "4 motors · drivers · camera · COIN D6 LiDAR",
    # Slide 5
    (5, 2): "04 · ARCHITECTURE",
    (5, 3): "How the system is built",
    (5, 4): "Each module has a dedicated responsibility",
    (5, 7): "CAMERA",
    (5, 8): "ticket barcode · video stream",
    (5, 11): "RASPBERRY PI 5",
    (5, 12): "kiosk · map · route",
    (5, 15): "ARDUINO MEGA",
    (5, 16): "drive · encoders",
    (5, 19): "DRIVE",
    (5, 20): "4 motors",
    (5, 28): "PASSENGER INTERFACE",
    (5, 29): "4 languages · ticket · destination selection",
    (5, 32): "Computing is separated: high-level logic runs on Raspberry Pi,\rwhile real-time motion control runs on Arduino.",
    # Slide 6
    (6, 2): "05 · NAVIGATION",
    (6, 3): "From manual control to autonomous routing",
    (6, 4): "What already works, what exists in software, and what still requires validation",
    (6, 11): "Working in prototype",
    (6, 12): "Arrow-key drive\r\rFour arrows control the robot",
    (6, 21): "Implemented in software",
    (6, 22): "Map and route\r\rThe robot builds a LiDAR map and plans A→B.",
    (6, 29): "Still to validate",
    (6, 30): "Field trials\r\rTesting in a real terminal with people.",
    (6, 33): "Navigation software is implemented; real airport operation is not yet claimed.",
    # Slide 7
    (7, 2): "06 · INTERFACE",
    (7, 3): "Clear at first glance",
    (7, 4): "Large actions, four languages, and quick ticket access",
    (7, 7): "4 languages",
    (7, 8): "RU · EN · 中文 · TT",
    (7, 10): "6 destinations",
    (7, 11): "4 are configurable",
    (7, 13): "Ticket",
    (7, 14): "camera or manual input",
    # Slide 8
    (8, 2): "07 · SAFETY",
    (8, 3): "Safety is built into the scenario",
    (8, 4): "The robot must help without creating new risks",
    (8, 7): "PROTOTYPE INTERNALS",
    (8, 12): "Drive watchdog",
    (8, 13): "No commands → stop",
    (8, 18): "Kiosk heartbeat",
    (8, 19): "Connection lost → escort cancelled",
    (8, 24): "Route control",
    (8, 25): "Only preconfigured destinations",
    (8, 30): "Protective body",
    (8, 31): "Required before deployment",
    (8, 36): "Status indication",
    (8, 37): "Shows robot state",
    # Slide 9
    (9, 2): "08 · DEVELOPMENT",
    (9, 3): "What was built in the project",
    (9, 7): "Scenario",
    (9, 8): "Passenger journey defined",
    (9, 11): "Chassis",
    (9, 12): "Mecanum platform assembled",
    (9, 15): "Electronics",
    (9, 16): "Pi, Mega, and drive connected",
    (9, 19): "Motion",
    (9, 20): "Remote robot control",
    (9, 23): "Development",
    (9, 24): "Kiosk and LiDAR modules added",
    (9, 26): "Modular design lets each part evolve independently",
    # Slide 10
    (10, 2): "09 · ECONOMICS",
    (10, 3): "Current prototype cost — about 90,000 RUB",
    (10, 5): "90,000",
    (10, 6): "rubles",
    (10, 7): "Chassis · motors · drivers · Arduino Mega\rRaspberry Pi 5 · LiDAR · camera · display · materials",
    (10, 9): "Why this matters",
    (10, 12): "accessible base for a functional prototype",
    (10, 15): "modular component replacement",
    (10, 18): "scaling as testing progresses",
    # Slide 11
    (11, 2): "10 · RESULTS",
    (11, 3): "What is achieved — and what comes next",
    (11, 5): "IMPLEMENTED / DEMO",
    (11, 8): "agile Mecanum platform",
    (11, 11): "split control: Pi + Arduino",
    (11, 14): "kiosk and ticket flow with demo data",
    (11, 17): "watchdog, heartbeat, and destination control",
    (11, 19): "REQUIRES VALIDATION",
    (11, 22): "LiDAR navigation trials in a terminal",
    (11, 25): "robustness around dynamic obstacles",
    (11, 28): "integration with real airport data",
    (11, 31): "industrial safe enclosure",
    # Slide 12
    (12, 4): "AEROPORTER",
    (12, 5): "Technology\rthat helps people\rfind their way",
    (12, 6): "Goal — transfer part of routine navigation to the robot\rand potentially reduce staff workload.",
    (12, 8): "Thank you for your attention",
}

NAME_OVERRIDES = {
    # PowerPoint may reorder connectors in Shapes(index); shape names stay stable.
    (2, 10): "TextBox 11",
    (2, 11): "TextBox 12",
    (2, 17): "TextBox 19",
    (2, 18): "TextBox 20",
    (2, 25): "TextBox 28",
    (2, 26): "TextBox 29",
    (7, 7): "TextBox 8",
    (7, 8): "TextBox 9",
    (7, 10): "TextBox 11",
    (7, 11): "TextBox 12",
    (7, 13): "TextBox 14",
    (7, 14): "TextBox 15",
}

EXTRA_TEXT_BY_NAME = {
    # Additional audience labels on the problem slide.
    (2, "TextBox 31"): "Especially vulnerable",
    (2, "TextBox 32"): "OLDER PEOPLE",
    (2, "TextBox 33"): "FAMILIES WITH CHILDREN",
    (2, "TextBox 34"): "INTERNATIONAL PASSENGERS",
}


def fit_text(shape) -> None:
    """Keep template geometry, shrink only when translated text needs it."""
    try:
        shape.TextFrame2.AutoSize = 2  # msoAutoSizeTextToFitShape
    except Exception:
        pass


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing template: {SOURCE}")

    app = win32.gencache.EnsureDispatch("PowerPoint.Application")
    app.Visible = -1
    pres = app.Presentations.Open(str(SOURCE), WithWindow=False)

    for (slide_no, shape_no), text in TEXT.items():
        shape_name = NAME_OVERRIDES.get((slide_no, shape_no), f"TextBox {shape_no}")
        shape = pres.Slides(slide_no).Shapes(shape_name)
        if not shape.HasTextFrame:
            continue
        shape.TextFrame.TextRange.Text = text
        fit_text(shape)

    for (slide_no, shape_name), text in EXTRA_TEXT_BY_NAME.items():
        shape = pres.Slides(slide_no).Shapes(shape_name)
        shape.TextFrame.TextRange.Text = text
        fit_text(shape)

    # Subtle motion without changing the visual design.
    for i in range(1, pres.Slides.Count + 1):
        slide = pres.Slides(i)
        transition = slide.SlideShowTransition
        transition.EntryEffect = c.ppEffectFade if i % 2 else c.ppEffectPushLeft
        transition.Duration = 0.55
        transition.AdvanceOnClick = -1

        seq = slide.TimeLine.MainSequence
        animated = 0
        for j in range(1, slide.Shapes.Count + 1):
            shape = slide.Shapes(j)
            try:
                if not shape.HasTextFrame or not shape.TextFrame.HasText:
                    continue
                value = shape.TextFrame.TextRange.Text.strip()
            except Exception:
                continue
            if value in {"AEROPORTER"} or value.isdigit() or value in {"✓", "→", "›"}:
                continue
            effect_id = c.msoAnimEffectFloat if animated < 2 else c.msoAnimEffectFade
            trigger = c.msoAnimTriggerWithPrevious if animated == 0 else c.msoAnimTriggerAfterPrevious
            try:
                effect = seq.AddEffect(shape, effect_id, trigger)
                effect.Timing.Duration = 0.35
                effect.Timing.TriggerDelayTime = 0.04 if animated else 0
                animated += 1
            except Exception:
                pass

    if DEST.exists():
        DEST.unlink()
    if PDF.exists():
        PDF.unlink()
    pres.SaveAs(str(DEST))
    pres.SaveAs(str(PDF), 32)
    print("saved", DEST)
    print("saved", PDF)
    print("slides", pres.Slides.Count, "effects", sum(pres.Slides(i).TimeLine.MainSequence.Count for i in range(1, pres.Slides.Count + 1)))
    pres.Close()
    app.Quit()


if __name__ == "__main__":
    main()
