# Mecanum + remote drive

## Web UI
http://172.17.118.159:8765/

- W/S or ↑↓ — forward / back  
- A/D or ←→ — strafe left / right (mecanum)  
- Q/E — rotate  
- Space / ■ — stop  

## Start on Pi
```bash
bash ~/robot_nav/start_drive_map.sh
```

## Arduino flash (required once for mecanum)
Open `MegaRobotBridge.ino` in Arduino IDE → Mega 2560 → Upload.

**PWM wiring for strafe:** each motor needs its own Enable:
| Motor | PWM | IN1 | IN2 |
|-------|-----|-----|-----|
| FL    | D5  | D8  | D9  |
| FR    | D6  | D10 | D11 |
| RL    | D44 | D12 | D13 |
| RR    | D45 | A0  | A1  |

If RL/RR Enable are still tied to D5/D6 (old tank wiring), forward/back/rotate still work; strafe needs D44/D45.

Until flash: old firmware accepts 2-arg velocity; driver sends 3-arg — flash Mega for full mecanum.
