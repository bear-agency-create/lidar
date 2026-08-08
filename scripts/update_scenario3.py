# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import zipfile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Possible old variants (exact / close)
OLD_VARIANTS = [
    "Третий сценарий. Пассажиру требуется помощь с перевозкой багажа. Робот берет вещи на себя и сопровождает пассажира через все этапы до посадки.",
]
NEW = (
    "Третий сценарий. Пассажиру требуется помощь только перевозкой багажа. "
    "Робот берет вещи на себя и проходит все этапы проверки багажа, "
    "клиенту остается только пройти личный досмотр и сесть в самолет."
)

RU_PATH = r"c:\Users\user\Desktop\AirPorter Выступление(рус.).docx"
RU_OUT = r"c:\Users\user\Desktop\AirPorter Выступление(рус.)-updated.docx"
EN_PATH = r"c:\Users\user\Desktop\AirPorter Speech (EN).docx"

EN_OLD = (
    "Scenario three. The passenger needs help with luggage. "
    "The robot takes the bags and escorts the passenger through all stages up to boarding."
)
EN_NEW = (
    "Scenario three. The passenger needs help only with luggage transport. "
    "The robot takes the bags and goes through all baggage-screening stages; "
    "the passenger only needs to complete personal security screening and board the aircraft."
)


def replace_in_docx(src: str, dst: str, old: str, new: str) -> bool:
    tmpdir = tempfile.mkdtemp()
    with zipfile.ZipFile(src, "r") as z:
        z.extractall(tmpdir)
    xml_path = os.path.join(tmpdir, "word", "document.xml")
    data = open(xml_path, encoding="utf-8").read()
    # Word may split text across <w:t> runs — try plain replace first,
    # then reconstruct by stripping tags for search.
    if old not in data:
        # Build plain text map by removing tags carefully for detection
        print("plain exact string not in XML for", os.path.basename(src))
        # Try replacing across split runs: replace character sequence if contiguous in stripped form
        # Fallback: replace unique substring pieces
        key = "Третий сценарий" if "Третий" in old else "Scenario three"
        if key not in data and "Сценарий" not in data:
            # show neighborhood
            pass
        # Replace by matching text nodes content rebuilt
        import xml.etree.ElementTree as ET

        root = ET.fromstring(data)
        # Find paragraph containing start of scenario 3
        target_start = "Третий сценарий" if "Третий" in old else "Scenario three"
        replaced = False
        for p in root.iter(f"{W}p"):
            texts = list(p.iter(f"{W}t"))
            full = "".join((t.text or "") for t in texts)
            if target_start in full and ("багаж" in full.lower() or "luggage" in full.lower() or "baggage" in full.lower()):
                # Put entire new text into first t, clear others
                if texts:
                    texts[0].text = new
                    for t in texts[1:]:
                        t.text = ""
                    replaced = True
                    break
        if not replaced:
            print("FAILED to find scenario-3 paragraph")
            return False
        data = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    else:
        data = data.replace(old, new)
        print("exact XML replace ok")

    open(xml_path, "w", encoding="utf-8").write(data)
    if os.path.exists(dst):
        os.remove(dst)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for root_dir, _, files in os.walk(tmpdir):
            for f in files:
                full = os.path.join(root_dir, f)
                arc = os.path.relpath(full, tmpdir).replace("\\", "/")
                z.write(full, arc)
    print("wrote", dst)
    return True


# RU
ok = False
for old in OLD_VARIANTS:
    try:
        ok = replace_in_docx(RU_PATH, RU_OUT, old, NEW)
        if ok:
            # try overwrite original
            try:
                shutil.copy2(RU_OUT, RU_PATH)
                print("overwrote original RU")
            except PermissionError:
                print("original RU locked — use updated file:", RU_OUT)
            break
    except Exception as e:
        print("RU error", e)

# EN via python-docx (cleaner)
from docx import Document

doc = Document(EN_PATH)
changed = False
for p in doc.paragraphs:
    if "Scenario three" in p.text and "luggage" in p.text.lower():
        p.text = EN_NEW
        changed = True
        break
if changed:
    doc.save(EN_PATH)
    print("EN updated")
else:
    print("EN scenario not found")
