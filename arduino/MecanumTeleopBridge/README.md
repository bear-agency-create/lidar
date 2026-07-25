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

Mild open-loop `TRIM_L` / `TRIM_R` + `BIAS`, plus rate-based encoder PID
(left/right tick delta each cycle — no cumulative runaway).

Live tuning (no reflash):

```
SET_TRIM 112 90
SET_BIAS 6
SET_PID 2.2 0.35 0.12
```

## Protocol

- `SET_ROBOT_VELOCITY <vx_mm_s> <vy_mm_s> <w_mrad_s>`
- `STOP` / `PING` / `ENC?` / `SET_POSE <x_mm> <y_mm> <th>`
- `SET_TRIM <L%> <R%>` / `SET_BIAS <pwm>` / `SET_PID <Kp> <Ki> <Kd>`
- Mega → `POS X=.. Y=.. Th=.. L=.. R=.. C=..`
