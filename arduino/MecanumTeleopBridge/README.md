# MecanumTeleopBridge

## Motors (identify-confirmed)

| Wheel | PWM | IN1 | IN2 |
|-------|-----|-----|-----|
| FL | 8 | 9 | 10 |
| FR | 7 | 5 | 6 |
| RL | 13 | 11 | 12 |
| RR | 2 | 3 | 4 |

## Encoders (pin-scan while spinning)

| Wheel | A | B |
|-------|---|---|
| FL | 50 | 51 |
| FR | 48 | 49 |
| RL | 52 | 53 |
| RR | 46 | 47 |

## Straight drive

Open-loop `TRIM_L` / `TRIM_R` plus closed-loop left/right encoder balance on forward/back.

Manual trim: `SET_TRIM 100 95` (percent of base PWM).

## Protocol

- `SET_ROBOT_VELOCITY <vx_mm_s> <vy_mm_s> <w_mrad_s>`
- `STOP` / `PING` / `ENC?` / `SET_POSE <x_mm> <y_mm> <th>`
- Mega → `POS X=.. Y=.. Th=.. L=.. R=..`
