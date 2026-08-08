# Build AirPorter presentation (RU + EN) via PowerPoint COM
$ErrorActionPreference = "Stop"
$Desktop = [Environment]::GetFolderPath("Desktop")
$Logo = "C:\Users\user\Projects\lidar\monitor\assets\kazan-airport-logo-white.png"
$Plane = "C:\Users\user\Projects\lidar\monitor\assets\realistic-airliner-balanced.png"

function RGB($r,$g,$b) { return $r + ($g * 256) + ($b * 65536) }

# Palette — airport night / terminal glass (not purple-AI)
$Navy     = RGB 11 31 51      # #0B1F33
$Navy2    = RGB 18 48 74      # #12304A
$Teal     = RGB 32 140 166    # #208CA6
$Sky      = RGB 90 178 210    # #5AB2D2
$Cream    = RGB 245 241 234   # #F5F1EA
$Ink      = RGB 18 28 38      # #121C26
$Muted    = RGB 90 110 128    # #5A6E80
$White    = RGB 255 255 255
$Accent   = RGB 212 160 74    # #D4A04A warm brass (sparse)

function Add-BlankSlide($pres) {
  # 12 = ppLayoutBlank
  return $pres.Slides.Add($pres.Slides.Count + 1, 12)
}

function Set-SlideBg($slide, $color) {
  $slide.FollowMasterBackground = $false
  $slide.Background.Fill.Solid()
  $slide.Background.Fill.ForeColor.RGB = $color
}

function Add-Rect($slide, $l, $t, $w, $h, $fill, $line=$null) {
  $s = $slide.Shapes.AddShape(1, $l, $t, $w, $h) # msoShapeRectangle
  $s.Fill.Solid(); $s.Fill.ForeColor.RGB = $fill
  if ($null -eq $line) { $s.Line.Visible = 0 } else { $s.Line.ForeColor.RGB = $line; $s.Line.Weight = 1 }
  return $s
}

function Add-Text($slide, $l, $t, $w, $h, $text, $size, $bold, $color, $align=1) {
  # align: 1=left 2=center 3=right
  $tb = $slide.Shapes.AddTextbox(1, $l, $t, $w, $h)
  $tf = $tb.TextFrame
  $tf.WordWrap = -1
  $tf.TextRange.Text = $text
  $tf.TextRange.Font.Name = "Calibri"
  $tf.TextRange.Font.Size = $size
  $tf.TextRange.Font.Bold = $(if ($bold) { -1 } else { 0 })
  $tf.TextRange.Font.Color.RGB = $color
  $tf.TextRange.ParagraphFormat.Alignment = $align
  $tf.MarginLeft = 6; $tf.MarginRight = 6; $tf.MarginTop = 4; $tf.MarginBottom = 4
  return $tb
}

function Add-Footer($slide, $label, $dark=$true) {
  $c = if ($dark) { $Sky } else { $Muted }
  Add-Text $slide 30 510 700 24 $label 11 $false $c 1 | Out-Null
  Add-Text $slide 780 510 160 24 "AirPorter" 11 $true $c 3 | Out-Null
}

function New-Pres($path, $lang) {
  $ppt = New-Object -ComObject PowerPoint.Application
  $ppt.Visible = -1
  $pres = $ppt.Presentations.Add()
  # Widescreen 16:9
  $pres.PageSetup.SlideWidth = 960
  $pres.PageSetup.SlideHeight = 540

  if ($lang -eq "ru") {
    $slides = Build-Ru $pres
  } else {
    $slides = Build-En $pres
  }

  if (Test-Path $path) { Remove-Item $path -Force }
  $pres.SaveAs($path)
  $pres.Close()
  $ppt.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
  [GC]::Collect()
  Write-Host "saved $path"
}

function Build-Ru($pres) {
  # --- Title ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Navy
  Add-Rect $s 0 0 18 540 $Teal | Out-Null
  Add-Rect $s 0 500 960 40 $Navy2 | Out-Null
  if (Test-Path $Logo) {
    try { $s.Shapes.AddPicture($Logo, $false, $true, 40, 36, 160, 42) | Out-Null } catch {}
  }
  if (Test-Path $Plane) {
    try { $s.Shapes.AddPicture($Plane, $false, $true, 560, 120, 360, 200) | Out-Null } catch {}
  }
  Add-Text $s 40 140 500 70 "AirPorter" 48 $true $White 1 | Out-Null
  Add-Text $s 40 210 520 80 "Мобильный робот-ассистент`nдля аэропорта" 26 $false $Sky 1 | Out-Null
  Add-Text $s 40 340 480 40 "Проект команды AirPorter" 16 $false $Cream 1 | Out-Null
  Add-Text $s 40 510 400 24 "Презентация проекта" 12 $false $Muted 1 | Out-Null

  # --- Problem ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 700 40 "Проблема" 28 $true $White 1 | Out-Null
  Add-Text $s 36 100 880 70 "Современный аэропорт — сложная система. Для многих пассажиров ориентирование становится серьёзной проблемой." 18 $false $Ink 1 | Out-Null

  $cards = @(
    @{t="Багаж"; d="Физическая нагрузка при перевозке вещей"},
    @{t="Навигация"; d="Сложная схема терминала и сервисов"},
    @{t="Язык"; d="Барьер при получении информации"}
  )
  $x = 36
  foreach ($c in $cards) {
    Add-Rect $s $x 200 280 200 $White (RGB 210 220 230) | Out-Null
    Add-Rect $s $x 200 280 8 $Teal | Out-Null
    Add-Text $s ($x+18) 230 244 40 $c.t 22 $true $Navy 1 | Out-Null
    Add-Text $s ($x+18) 290 244 80 $c.d 16 $false $Muted 1 | Out-Null
    $x += 300
  }
  Add-Footer $s "Слайд 2 · Проблема" $false

  # --- Solution overview ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Решение — AirPorter" 28 $true $White 1 | Out-Null
  Add-Text $s 36 100 880 60 "Робот-ассистент помогает пассажиру пройти путь от старта до цели с учётом его потребностей." 18 $false $Ink 1 | Out-Null

  $steps = @(
    @{n="01"; t="Скан билета"; d="Рейс, пассажир, базовые данные"},
    @{n="02"; t="Информация"; d="Выход, время, сервисы на экране"},
    @{n="03"; t="Сценарий"; d="Инфо · escort · только багаж"}
  )
  $x = 36
  foreach ($st in $steps) {
    Add-Rect $s $x 200 280 220 $Navy | Out-Null
    Add-Text $s ($x+20) 220 240 36 $st.n 28 $true $Accent 1 | Out-Null
    Add-Text $s ($x+20) 270 240 40 $st.t 20 $true $White 1 | Out-Null
    Add-Text $s ($x+20) 320 240 70 $st.d 15 $false $Sky 1 | Out-Null
    $x += 300
  }
  Add-Footer $s "Слайд 3 · Решение" $false

  # --- 3 scenarios ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Три сценария работы" 28 $true $White 1 | Out-Null

  $sc = @(
    @{n="1"; t="Только информация"; d="Маршрут и данные на экране. Сессия завершается."},
    @{n="2"; t="Сопровождение"; d="Маршрут через регистрацию, сервисы или выход. Робот ведёт пассажира."},
    @{n="3"; t="Только багаж"; d="Робот проходит проверку багажа. Пассажиру — личный досмотр и посадка."}
  )
  $y = 100
  foreach ($item in $sc) {
    Add-Rect $s 36 $y 60 70 $Teal | Out-Null
    Add-Text $s 48 ($y+16) 40 40 $item.n 24 $true $White 2 | Out-Null
    Add-Rect $s 110 $y 814 70 $White (RGB 210 220 230) | Out-Null
    Add-Text $s 130 ($y+8) 780 28 $item.t 18 $true $Navy 1 | Out-Null
    Add-Text $s 130 ($y+36) 780 28 $item.d 14 $false $Muted 1 | Out-Null
    $y += 90
  }
  Add-Footer $s "Слайд 3 · Сценарии" $false

  # --- Hardware ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Аппаратная платформа" 28 $true $White 1 | Out-Null
  Add-Text $s 36 95 880 36 "Первый рабочий прототип" 16 $false $Muted 1 | Out-Null

  $hw = @(
    @{t="Raspberry Pi 5"; d="16 ГБ · ROS 2 Jazzy · лидар · камера · логика"},
    @{t="Arduino Mega 2560"; d="Энкодеры · точное управление моторами"},
    @{t="Mecanum + COIN D6"; d="Омни-движение · лидар · экран 10,1`""},
    @{t="Привод"; d="L298N · моторы JGB37-520"}
  )
  $coords = @(@(36,150),@(490,150),@(36,320),@(490,320))
  for ($i=0; $i -lt 4; $i++) {
    $cx = $coords[$i][0]; $cy = $coords[$i][1]
    Add-Rect $s $cx $cy 430 140 $White (RGB 210 220 230) | Out-Null
    Add-Rect $s $cx $cy 8 140 $Teal | Out-Null
    Add-Text $s ($cx+24) ($cy+24) 380 36 $hw[$i].t 20 $true $Navy 1 | Out-Null
    Add-Text $s ($cx+24) ($cy+70) 380 50 $hw[$i].d 15 $false $Muted 1 | Out-Null
  }
  Add-Footer $s "Слайд 4 · Железо" $false

  # --- Navigation ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Navy
  Add-Rect $s 0 0 18 540 $Teal | Out-Null
  Add-Text $s 50 60 860 50 "Навигация" 32 $true $White 1 | Out-Null
  $nav = @(
    "Карта помещения по лидару",
    "Оценка позы · габариты корпуса · энкодеры",
    "Маршрут и объезд препятствий",
    "Проезд по точкам и операторский контроль"
  )
  $y = 150
  foreach ($line in $nav) {
    Add-Rect $s 50 $y 18 18 $Accent | Out-Null
    Add-Text $s 86 ($y-6) 800 36 $line 20 $false $Cream 1 | Out-Null
    $y += 60
  }
  Add-Footer $s "Слайд 5 · Навигация" $true

  # --- UI ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Интерфейс пассажира" 28 $true $White 1 | Out-Null
  Add-Text $s 36 100 880 50 "Киоск на сенсорном экране: регистрация, посадка, багаж, информация и другие точки терминала." 17 $false $Ink 1 | Out-Null
  $langs = @("Русский","English","Татарча")
  $x = 36
  foreach ($L in $langs) {
    Add-Rect $s $x 200 280 100 $Navy | Out-Null
    Add-Text $s $x 230 280 40 $L 22 $true $White 2 | Out-Null
    $x += 300
  }
  Add-Text $s 36 340 880 50 "Простой интерфейс в тематике аэропорта — понятен без инструкций." 16 $false $Muted 1 | Out-Null
  Add-Footer $s "Слайд 6 · Интерфейс" $false

  # --- Safety ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Безопасность" 28 $true $White 1 | Out-Null
  $safe = @(
    "Стоп при потере связи",
    "Контроль маршрута",
    "Распознавание препятствий",
    "Корпус из оргстекла",
    "Небольшой клиренс",
    "Световая индикация"
  )
  $i = 0
  foreach ($item in $safe) {
    $col = $i % 3; $row = [math]::Floor($i / 3)
    $x = 36 + $col * 300; $y = 120 + $row * 150
    Add-Rect $s $x $y 280 120 $White (RGB 210 220 230) | Out-Null
    Add-Rect $s $x $y 280 6 $Accent | Out-Null
    Add-Text $s ($x+20) ($y+40) 240 50 $item 16 $true $Navy 1 | Out-Null
    $i++
  }
  Add-Footer $s "Слайд 7 · Безопасность" $false

  # --- Prototype ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Navy
  Add-Rect $s 0 0 18 540 $Accent | Out-Null
  Add-Text $s 50 80 860 50 "Первый прототип" 32 $true $White 1 | Out-Null
  Add-Text $s 50 160 860 200 "Интерактивное меню · проезд по точкам · ориентирование в пространстве · перевозка груза" 24 $false $Sky 1 | Out-Null
  Add-Text $s 50 360 860 40 "Работающая платформа, готовая к демонстрации и доработке." 16 $false $Cream 1 | Out-Null
  Add-Footer $s "Слайд 8 · Прототип" $true

  # --- Experts + Economics ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Оценка и экономика" 28 $true $White 1 | Out-Null
  Add-Rect $s 36 120 430 300 $Navy | Out-Null
  Add-Text $s 56 150 390 40 "Эксперты" 20 $true $Accent 1 | Out-Null
  Add-Text $s 56 210 390 160 "Положительная оценка авиационной отрасли. Интерес аэропорта к дальнейшим испытаниям." 16 $false $Cream 1 | Out-Null
  Add-Rect $s 490 120 430 300 $White (RGB 210 220 230) | Out-Null
  Add-Text $s 510 150 390 40 "Стоимость прототипа" 20 $true $Navy 1 | Out-Null
  Add-Text $s 510 220 390 60 "~ 90 000 ₽" 36 $true $Teal 1 | Out-Null
  Add-Text $s 510 300 390 80 "Модульная конструкция — модернизация без полной замены." 15 $false $Muted 1 | Out-Null
  Add-Footer $s "Слайды 9–10" $false

  # --- Future ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Планы на будущее" 28 $true $White 1 | Out-Null
  $plans = @(
    "Металлический каркас и промышленные Mecanum",
    "Промышленная электроника и сенсорика (в т.ч. 360°)",
    "Приложение для пассажира и панель флота",
    "Хаб зарядки и обслуживания",
    "Испытания в реальных сценариях аэропорта"
  )
  $y = 110
  $n = 1
  foreach ($p in $plans) {
    Add-Text $s 50 $y 60 36 ("{0:D2}" -f $n) 18 $true $Teal 1 | Out-Null
    Add-Text $s 110 $y 800 36 $p 17 $false $Ink 1 | Out-Null
    $y += 55; $n++
  }
  Add-Footer $s "Слайд 11 · Планы" $false

  # --- Closing ---
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Navy
  Add-Rect $s 0 0 18 540 $Teal | Out-Null
  if (Test-Path $Logo) {
    try { $s.Shapes.AddPicture($Logo, $false, $true, 380, 80, 200, 52) | Out-Null } catch {}
  }
  Add-Text $s 80 200 800 60 "Спасибо за внимание!" 36 $true $White 2 | Out-Null
  Add-Text $s 80 280 800 40 "Команда AirPorter" 22 $false $Sky 2 | Out-Null
  Add-Text $s 80 400 800 30 "Вопросы приветствуются" 14 $false $Muted 2 | Out-Null
}

function Build-En($pres) {
  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Navy
  Add-Rect $s 0 0 18 540 $Teal | Out-Null
  if (Test-Path $Logo) { try { $s.Shapes.AddPicture($Logo, $false, $true, 40, 36, 160, 42) | Out-Null } catch {} }
  if (Test-Path $Plane) { try { $s.Shapes.AddPicture($Plane, $false, $true, 560, 120, 360, 200) | Out-Null } catch {} }
  Add-Text $s 40 140 500 70 "AirPorter" 48 $true $White 1 | Out-Null
  Add-Text $s 40 210 520 80 "A mobile robot assistant`nfor the airport" 26 $false $Sky 1 | Out-Null
  Add-Text $s 40 340 480 40 "Presented by the AirPorter team" 16 $false $Cream 1 | Out-Null

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 700 40 "The problem" 28 $true $White 1 | Out-Null
  Add-Text $s 36 100 880 70 "Airports are complex. For many passengers, finding the way is a serious challenge." 18 $false $Ink 1 | Out-Null
  $cards = @(
    @{t="Luggage"; d="Physical strain when carrying bags"},
    @{t="Navigation"; d="Complex terminal layout and services"},
    @{t="Language"; d="Barrier when getting information"}
  )
  $x = 36
  foreach ($c in $cards) {
    Add-Rect $s $x 200 280 200 $White (RGB 210 220 230) | Out-Null
    Add-Rect $s $x 200 280 8 $Teal | Out-Null
    Add-Text $s ($x+18) 230 244 40 $c.t 22 $true $Navy 1 | Out-Null
    Add-Text $s ($x+18) 290 244 80 $c.d 16 $false $Muted 1 | Out-Null
    $x += 300
  }
  Add-Footer $s "Slide 2 · Problem" $false

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "The solution — AirPorter" 28 $true $White 1 | Out-Null
  Add-Text $s 36 100 880 50 "A robot assistant that helps passengers travel from start to destination." 18 $false $Ink 1 | Out-Null
  $steps = @(
    @{n="01"; t="Scan ticket"; d="Flight and passenger data"},
    @{n="02"; t="Show info"; d="Gate, time, services on screen"},
    @{n="03"; t="Scenario"; d="Info · escort · luggage-only"}
  )
  $x = 36
  foreach ($st in $steps) {
    Add-Rect $s $x 200 280 220 $Navy | Out-Null
    Add-Text $s ($x+20) 220 240 36 $st.n 28 $true $Accent 1 | Out-Null
    Add-Text $s ($x+20) 270 240 40 $st.t 20 $true $White 1 | Out-Null
    Add-Text $s ($x+20) 320 240 70 $st.d 15 $false $Sky 1 | Out-Null
    $x += 300
  }
  Add-Footer $s "Slide 3 · Solution" $false

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Three scenarios" 28 $true $White 1 | Out-Null
  $sc = @(
    @{n="1"; t="Information only"; d="Route and data on screen. Session ends."},
    @{n="2"; t="Escort"; d="Route via check-in, services, or gate. Robot guides the passenger."},
    @{n="3"; t="Luggage only"; d="Robot handles baggage screening. Passenger does security and boards."}
  )
  $y = 100
  foreach ($item in $sc) {
    Add-Rect $s 36 $y 60 70 $Teal | Out-Null
    Add-Text $s 48 ($y+16) 40 40 $item.n 24 $true $White 2 | Out-Null
    Add-Rect $s 110 $y 814 70 $White (RGB 210 220 230) | Out-Null
    Add-Text $s 130 ($y+8) 780 28 $item.t 18 $true $Navy 1 | Out-Null
    Add-Text $s 130 ($y+36) 780 28 $item.d 14 $false $Muted 1 | Out-Null
    $y += 90
  }
  Add-Footer $s "Slide 3 · Scenarios" $false

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Hardware platform" 28 $true $White 1 | Out-Null
  $hw = @(
    @{t="Raspberry Pi 5"; d="16 GB · ROS 2 Jazzy · lidar · camera · logic"},
    @{t="Arduino Mega 2560"; d="Encoders · precise motor control"},
    @{t="Mecanum + COIN D6"; d="Omni drive · lidar · 10.1`" screen"},
    @{t="Drive"; d="L298N · JGB37-520 motors"}
  )
  $coords = @(@(36,150),@(490,150),@(36,320),@(490,320))
  for ($i=0; $i -lt 4; $i++) {
    $cx=$coords[$i][0]; $cy=$coords[$i][1]
    Add-Rect $s $cx $cy 430 140 $White (RGB 210 220 230) | Out-Null
    Add-Rect $s $cx $cy 8 140 $Teal | Out-Null
    Add-Text $s ($cx+24) ($cy+24) 380 36 $hw[$i].t 20 $true $Navy 1 | Out-Null
    Add-Text $s ($cx+24) ($cy+70) 380 50 $hw[$i].d 15 $false $Muted 1 | Out-Null
  }
  Add-Footer $s "Slide 4 · Hardware" $false

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Navy
  Add-Rect $s 0 0 18 540 $Teal | Out-Null
  Add-Text $s 50 60 860 50 "Navigation" 32 $true $White 1 | Out-Null
  foreach ($pair in @(@(150,"Lidar indoor mapping"),@(210,"Pose · footprint · encoders"),@(270,"Routing and obstacle avoidance"),@(330,"Waypoints and operator control"))) {
    Add-Rect $s 50 $pair[0] 18 18 $Accent | Out-Null
    Add-Text $s 86 ($pair[0]-6) 800 36 $pair[1] 20 $false $Cream 1 | Out-Null
  }
  Add-Footer $s "Slide 5 · Navigation" $true

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Passenger interface" 28 $true $White 1 | Out-Null
  Add-Text $s 36 100 880 50 "Touchscreen kiosk: check-in, boarding, baggage, information, and more." 17 $false $Ink 1 | Out-Null
  $x=36; foreach ($L in @("Russian","English","Tatar")) {
    Add-Rect $s $x 200 280 100 $Navy | Out-Null
    Add-Text $s $x 230 280 40 $L 22 $true $White 2 | Out-Null
    $x += 300
  }
  Add-Footer $s "Slide 6 · Interface" $false

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Safety" 28 $true $White 1 | Out-Null
  $safe = @("Stop on link loss","Route monitoring","Obstacle detection","Acrylic body","Low clearance","Status lights")
  $i=0; foreach ($item in $safe) {
    $col=$i%3; $row=[math]::Floor($i/3)
    $x=36+$col*300; $y=120+$row*150
    Add-Rect $s $x $y 280 120 $White (RGB 210 220 230) | Out-Null
    Add-Rect $s $x $y 280 6 $Accent | Out-Null
    Add-Text $s ($x+20) ($y+40) 240 50 $item 16 $true $Navy 1 | Out-Null
    $i++
  }
  Add-Footer $s "Slide 7 · Safety" $false

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Navy
  Add-Rect $s 0 0 18 540 $Accent | Out-Null
  Add-Text $s 50 80 860 50 "First prototype" 32 $true $White 1 | Out-Null
  Add-Text $s 50 160 860 200 "Interactive menu · waypoint travel · spatial orientation · load carrying" 24 $false $Sky 1 | Out-Null
  Add-Footer $s "Slide 8 · Prototype" $true

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Feedback and economics" 28 $true $White 1 | Out-Null
  Add-Rect $s 36 120 430 300 $Navy | Out-Null
  Add-Text $s 56 150 390 40 "Experts" 20 $true $Accent 1 | Out-Null
  Add-Text $s 56 210 390 160 "Positive aviation-industry feedback. Airport interest in further testing." 16 $false $Cream 1 | Out-Null
  Add-Rect $s 490 120 430 300 $White (RGB 210 220 230) | Out-Null
  Add-Text $s 510 150 390 40 "Prototype cost" 20 $true $Navy 1 | Out-Null
  Add-Text $s 510 220 390 60 "~ 90,000 RUB" 32 $true $Teal 1 | Out-Null
  Add-Text $s 510 300 390 80 "Modular design — upgrade without full replacement." 15 $false $Muted 1 | Out-Null
  Add-Footer $s "Slides 9–10" $false

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Cream
  Add-Rect $s 0 0 960 70 $Navy | Out-Null
  Add-Text $s 36 18 800 40 "Future plans" 28 $true $White 1 | Out-Null
  $plans = @(
    "Metal frame and industrial Mecanum wheels",
    "Industrial electronics and sensing (incl. 360°)",
    "Passenger app and fleet dashboard",
    "Charging and service hub",
    "Real airport scenario trials"
  )
  $y=110; $n=1
  foreach ($p in $plans) {
    Add-Text $s 50 $y 60 36 ("{0:D2}" -f $n) 18 $true $Teal 1 | Out-Null
    Add-Text $s 110 $y 800 36 $p 17 $false $Ink 1 | Out-Null
    $y += 55; $n++
  }
  Add-Footer $s "Slide 11 · Future" $false

  $s = Add-BlankSlide $pres
  Set-SlideBg $s $Navy
  Add-Rect $s 0 0 18 540 $Teal | Out-Null
  if (Test-Path $Logo) { try { $s.Shapes.AddPicture($Logo, $false, $true, 380, 80, 200, 52) | Out-Null } catch {} }
  Add-Text $s 80 200 800 60 "Thank you!" 40 $true $White 2 | Out-Null
  Add-Text $s 80 280 800 40 "The AirPorter Team" 22 $false $Sky 2 | Out-Null
  Add-Text $s 80 400 800 30 "Questions welcome" 14 $false $Muted 2 | Out-Null
}

New-Pres (Join-Path $Desktop "AirPorter Presentation (RU).pptx") "ru"
New-Pres (Join-Path $Desktop "AirPorter Presentation (EN).pptx") "en"
Write-Host "ALL DONE"
