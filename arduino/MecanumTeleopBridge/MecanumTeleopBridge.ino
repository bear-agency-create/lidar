/*
  MecanumTeleopBridge — mecanum drive with per-wheel velocity alignment

  Motions: forward / back (vx), strafe left / right (vy), rotate (w).

  Alignment: encoders have very different resolutions per wheel.
  FL encoder is dead (always 0); FR/RL/RR run per-wheel PI velocity loops
  (tick rate normalized by each wheel's calTps). FL uses feedforward and
  mirrors FR on forward/back. Chassis + per-wheel ramps smooth teleop thrust.
  Odometry is solved from FR/RL/RR (3 wheels determine 3-DOF motion).

  Serial protocol (115200, \n terminated):
    SET_ROBOT_VELOCITY vx vy w   vx/vy ~500 = full, w ~1500 = full
    w/s/a/d                      fwd / back / strafe L / strafe R
    q/e (z/c)                    rotate CCW / CW
    STOP                         smooth coast-down (shared ramp)
    HARD_STOP / BRAKE / x / spc  immediate brake (all wheels)
    PING                         -> PONG
    RESET_ODOM                   zero encoders + pose -> ODOM_OK
    SET_POSE x_mm y_mm th        override pose -> POSE_OK
    ENC?                         raw per-wheel encoder counts
    SET_PIDV kp ki               velocity-loop gains x1000 (0 0 = open-loop equal)
    SET_CAL fl fr rl rr          full-scale ticks/s per wheel
    SET_WSCALE fl fr rl rr       per-wheel FF scale percent (100 = nominal)
    SET_FRB pct                  FR reverse-direction scale in percent
    SET_FRF pct                  FR forward-direction scale in percent

  Telemetry every 80 ms (L/R are resolution-normalized tick sums):
    POS X=<mm> Y=<mm> Th=<rad> L=<ticks> R=<ticks> C=<max PI corr>
*/

#include <math.h>
#include <string.h>
#include <stdlib.h>

static const uint8_t FL_PWM = 8,  FL_IN1 = 9,  FL_IN2 = 10;
static const uint8_t FR_PWM = 7,  FR_IN1 = 5,  FR_IN2 = 6;
static const uint8_t RL_PWM = 13, RL_IN1 = 11, RL_IN2 = 12;
static const uint8_t RR_PWM = 2,  RR_IN1 = 3,  RR_IN2 = 4;

static const uint8_t ENC_FL_A = 50, ENC_FL_B = 51;
static const uint8_t ENC_FR_A = 48, ENC_FR_B = 49;
static const uint8_t ENC_RL_A = 52, ENC_RL_B = 53;
static const uint8_t ENC_RR_A = 46, ENC_RR_B = 47;

// FR -1 fixes forward. RL driven by driveRL() with explicit pin states both ways.
static const int SIGN_FL = -1, SIGN_FR = -1, SIGN_RL = +1, SIGN_RR = +1;
static const int ENC_SIGN_FL = -1, ENC_SIGN_FR = -1, ENC_SIGN_RL = +1, ENC_SIGN_RR = -1;

static const int BASE_PWM = 255;
static const int MAX_PWM = 255;

static const float WHEEL_DIAMETER_MM = 65.0f;
static const float TRACK_WIDTH_MM = 560.0f;
static const long  TICKS_PER_REV = 20;

static const unsigned long CMD_TIMEOUT_MS = 1200;
static const unsigned long POS_PERIOD_MS = 80;
static const unsigned long CTRL_PERIOD_MS = 25;

// Full-scale ticks/s per wheel at mix 1.0 (PWM ~200), measured 2026-07-26 new floor.
static float calTps[4] = {510.0f, 734.0f, 2103.0f, 1389.0f};   // FL FR RL RR

// Wheels with trustworthy encoders (index: 0=FL 1=FR 2=RL 3=RR)
// Encoders unreliable for equal max speed — open-loop WSCALE only.
static const bool encTrusted[4] = {false, false, false, false};

// FR extra direction scales (on top of wheelScale[1]).
static float frRevScale = 1.00f;
static float frFwdScale = 1.00f;

// Open-loop max thrust — WSCALE helps mid-throttle; full cmd saturates PWM.
static float wheelScale[4] = {2.00f, 2.00f, 2.00f, 2.00f};

// Per-wheel velocity PI (normalized units). Default off for equal motion.
static float velKp = 0.0f;
static float velKi = 0.0f;
static const float VEL_INT_MAX = 0.35f;
static const float EMA_ALPHA = 0.38f;
// Smooth start: jump to 50%, then ramp to full. Yaw axis a bit snappier.
static const float RAMP_START = 0.50f;
static const float RAMP_UP = 0.085f;
static const float RAMP_DOWN = 0.060f;
static const float WHEEL_RAMP_UP = 0.100f;
static const float WHEEL_RAMP_DOWN = 0.070f;
static const int PWM_FLOOR = 128;   // 50% of 255 — never creep from 0 under load

static int cmd_vx = 0, cmd_vy = 0, cmd_w_mrad = 0;
static unsigned long lastCmdMs = 0;
static float x_mm = 0, y_mm = 0, th = 0;
static char lineBuf[140];
static uint8_t lineLen = 0;

volatile long encFL = 0, encFR = 0, encRL = 0, encRR = 0;
static uint8_t prevFLA, prevFRA, prevRLA, prevRRA;

// Control state
static long prevTicks[4] = {0, 0, 0, 0};
static float rampX = 0.0f, rampY = 0.0f, rampW = 0.0f;
static float rampOut[4] = {0.0f, 0.0f, 0.0f, 0.0f};
static float emaTps[4] = {0, 0, 0, 0};
static float velInt[4] = {0, 0, 0, 0};
static float lastCorr = 0.0f;   // max |PI correction| for telemetry
static bool hardBrake = false;
static unsigned long brakeUntilMs = 0;

static float mmPerTick() {
  return (PI * WHEEL_DIAMETER_MM) / (float)TICKS_PER_REV;
}

static inline void quadTick(uint8_t a, uint8_t b, uint8_t *prevA, volatile long *cnt, int sign) {
  if (a == *prevA) return;
  *prevA = a;
  if (a == b) (*cnt) += sign;
  else (*cnt) -= sign;
}

static void pollEncoders() {
  quadTick(digitalRead(ENC_FL_A), digitalRead(ENC_FL_B), &prevFLA, &encFL, ENC_SIGN_FL);
  quadTick(digitalRead(ENC_FR_A), digitalRead(ENC_FR_B), &prevFRA, &encFR, ENC_SIGN_FR);
  quadTick(digitalRead(ENC_RL_A), digitalRead(ENC_RL_B), &prevRLA, &encRL, ENC_SIGN_RL);
  quadTick(digitalRead(ENC_RR_A), digitalRead(ENC_RR_B), &prevRRA, &encRR, ENC_SIGN_RR);
}

// Resolution-normalized counts (units of the average wheel's ticks)
static float calMean() {
  return 0.25f * (calTps[0] + calTps[1] + calTps[2] + calTps[3]);
}
static float normFL() { return (float)encFL * calMean() / calTps[0]; }
static float normFR() { return (float)encFR * calMean() / calTps[1]; }
static float normRL() { return (float)encRL * calMean() / calTps[2]; }
static float normRR() { return (float)encRR * calMean() / calTps[3]; }

static int clampPwm(int v) {
  if (v < 0) v = 0;
  if (v > MAX_PWM) v = MAX_PWM;
  return v;
}

static float clampf(float v, float lo, float hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

static void motor(uint8_t pwm, uint8_t in1, uint8_t in2, int dir, int sign, int speed) {
  int d = dir * sign;
  if (d > 0) {
    digitalWrite(in1, HIGH); digitalWrite(in2, LOW); analogWrite(pwm, clampPwm(speed));
  } else if (d < 0) {
    digitalWrite(in1, LOW); digitalWrite(in2, HIGH); analogWrite(pwm, clampPwm(speed));
  } else {
    digitalWrite(in1, LOW); digitalWrite(in2, LOW); analogWrite(pwm, 0);
  }
}

static void motorCoast(uint8_t pwm, uint8_t in1, uint8_t in2) {
  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
  analogWrite(pwm, 0);
}

static void motorBrake(uint8_t pwm, uint8_t in1, uint8_t in2) {
  // Active short-brake on typical dual-H bridges (IN1=IN2=HIGH).
  digitalWrite(in1, HIGH); digitalWrite(in2, HIGH); analogWrite(pwm, 255);
}

static int lastDriveDir[4] = {0, 0, 0, 0};

static void driveOneIdx(int idx, uint8_t pwm, uint8_t in1, uint8_t in2, int sign, float v) {
  int dir = 0;
  if (v > 0.008f) dir = +1;
  else if (v < -0.008f) dir = -1;
  if (dir == 0) {
    motorCoast(pwm, in1, in2);
    lastDriveDir[idx] = 0;
    return;
  }
  if (lastDriveDir[idx] != 0 && lastDriveDir[idx] != dir) {
    motorCoast(pwm, in1, in2);
    delayMicroseconds(250);
  }
  float mag = clampf(fabsf(v), 0.0f, 1.0f);
  // Smooth power: command 0.5 → ~50% PWM, 1.0 → full; never below PWM_FLOOR while moving.
  int spd = (int)(mag * (float)BASE_PWM + 0.5f);
  if (spd < PWM_FLOOR) spd = PWM_FLOOR;
  if (mag >= 0.42f) spd = BASE_PWM;  // hit full PWM early under load
  motor(pwm, in1, in2, dir, sign, clampPwm(spd));
  lastDriveDir[idx] = dir;
}

// FL: explicit IN levels both ways (same class of sticky H-bridge as RL).
// Logical +v (chassis forward for this wheel): IN1=HIGH IN2=LOW after SIGN_FL=-1
// → electrical d<0 → IN1=LOW IN2=HIGH. Keep that mapping explicit here.
static void driveFL(float v) {
  int dir = 0;
  if (v > 0.008f) dir = +1;
  else if (v < -0.008f) dir = -1;
  if (dir == 0) {
    motorCoast(FL_PWM, FL_IN1, FL_IN2);
    lastDriveDir[0] = 0;
    return;
  }
  if (lastDriveDir[0] != 0 && lastDriveDir[0] != dir) {
    motorCoast(FL_PWM, FL_IN1, FL_IN2);
    delayMicroseconds(300);
  }
  float mag = clampf(fabsf(v), 0.0f, 1.0f);
  int spd = (int)(mag * (float)BASE_PWM + 0.5f);
  if (spd < PWM_FLOOR) spd = PWM_FLOOR;
  if (mag >= 0.42f) spd = BASE_PWM;
  spd = clampPwm(spd);
  // SIGN_FL = -1: logical +fwd → IN1 LOW, IN2 HIGH; logical -rev → IN1 HIGH, IN2 LOW.
  if (dir > 0) {
    digitalWrite(FL_IN1, LOW);
    digitalWrite(FL_IN2, HIGH);
  } else {
    digitalWrite(FL_IN1, HIGH);
    digitalWrite(FL_IN2, LOW);
  }
  analogWrite(FL_PWM, spd);
  lastDriveDir[0] = dir;
}

// RL: both directions use explicit IN levels (avoid flaky d<0 path on this channel).
// Forward: IN2=HIGH IN1=LOW. Reverse: IN1=HIGH IN2=LOW. PWM=13.
static void driveRL(float v) {
  int dir = 0;
  if (v > 0.008f) dir = +1;
  else if (v < -0.008f) dir = -1;
  if (dir == 0) {
    motorCoast(RL_PWM, RL_IN1, RL_IN2);
    lastDriveDir[2] = 0;
    return;
  }
  if (lastDriveDir[2] != 0 && lastDriveDir[2] != dir) {
    motorCoast(RL_PWM, RL_IN1, RL_IN2);
    delayMicroseconds(300);
  }
  float mag = clampf(fabsf(v), 0.0f, 1.0f);
  int spd = (int)(mag * (float)BASE_PWM + 0.5f);
  if (spd < PWM_FLOOR) spd = PWM_FLOOR;
  if (mag >= 0.42f) spd = BASE_PWM;
  spd = clampPwm(spd);
  if (dir > 0) {
    digitalWrite(RL_IN1, LOW);
    digitalWrite(RL_IN2, HIGH);
  } else {
    digitalWrite(RL_IN1, HIGH);
    digitalWrite(RL_IN2, LOW);
  }
  analogWrite(RL_PWM, spd);
  lastDriveDir[2] = dir;
}

static void resetControl() {
  rampX = rampY = rampW = 0.0f;
  for (int i = 0; i < 4; i++) {
    rampOut[i] = 0.0f;
    velInt[i] = 0.0f;
    emaTps[i] = 0.0f;
    lastDriveDir[i] = 0;
  }
  lastCorr = 0.0f;
  hardBrake = false;
  brakeUntilMs = 0;
}

static void stopHard() {
  motorBrake(FL_PWM, FL_IN1, FL_IN2);
  motorBrake(FR_PWM, FR_IN1, FR_IN2);
  motorBrake(RL_PWM, RL_IN1, RL_IN2);
  motorBrake(RR_PWM, RR_IN1, RR_IN2);
  cmd_vx = cmd_vy = cmd_w_mrad = 0;
  rampX = rampY = rampW = 0.0f;
  for (int i = 0; i < 4; i++) {
    rampOut[i] = 0.0f;
    velInt[i] = 0.0f;
    emaTps[i] = 0.0f;
  }
  lastCorr = 0.0f;
  hardBrake = true;
  brakeUntilMs = millis() + 80;
}

static void stopSoft() {
  // Teleop stop must cut FL immediately — soft coast left FL spinning
  // on this chassis (sticky forward half-bridge + PWM floor).
  cmd_vx = cmd_vy = cmd_w_mrad = 0;
  lastCmdMs = millis();
  rampX = rampY = rampW = 0.0f;
  for (int i = 0; i < 4; i++) {
    rampOut[i] = 0.0f;
    velInt[i] = 0.0f;
    emaTps[i] = 0.0f;
    lastDriveDir[i] = 0;
  }
  lastCorr = 0.0f;
  hardBrake = false;
  brakeUntilMs = 0;
  motorCoast(FL_PWM, FL_IN1, FL_IN2);
  motorCoast(FR_PWM, FR_IN1, FR_IN2);
  motorCoast(RL_PWM, RL_IN1, RL_IN2);
  motorCoast(RR_PWM, RR_IN1, RR_IN2);
}

static void coastMotors() {
  motorCoast(FL_PWM, FL_IN1, FL_IN2);
  motorCoast(FR_PWM, FR_IN1, FR_IN2);
  motorCoast(RL_PWM, RL_IN1, RL_IN2);
  motorCoast(RR_PWM, RR_IN1, RR_IN2);
}

static float slewToward(float current, float target, float upStep, float downStep) {
  // Kick-start: leave standstill at 50% thrust, then smooth to target.
  if (fabsf(current) < 0.08f && fabsf(target) >= RAMP_START) {
    return (target > 0.0f) ? RAMP_START : -RAMP_START;
  }
  float d = target - current;
  bool accel = fabsf(target) > fabsf(current) + 1e-4f;
  float step = accel ? upStep : downStep;
  if (d > step) d = step;
  if (d < -step) d = -step;
  return current + d;
}

static bool rampsActive() {
  return fabsf(rampX) > 0.015f || fabsf(rampY) > 0.015f || fabsf(rampW) > 0.015f;
}

static bool wheelRampsActive() {
  for (int i = 0; i < 4; i++) {
    if (fabsf(rampOut[i]) > 0.015f) return true;
  }
  return false;
}

static void applyMotors(float dt, const long dTicks[4]) {
  if (hardBrake) {
    if ((long)(millis() - brakeUntilMs) < 0) {
      motorBrake(FL_PWM, FL_IN1, FL_IN2);
      motorBrake(FR_PWM, FR_IN1, FR_IN2);
      motorBrake(RL_PWM, RL_IN1, RL_IN2);
      motorBrake(RR_PWM, RR_IN1, RR_IN2);
      return;
    }
    hardBrake = false;
    brakeUntilMs = 0;
    coastMotors();
    return;
  }

  // Forward/back: smooth ramp. Crab (vy) and tank yaw (w): snap to full immediately.
  float tgtX = clampf((float)cmd_vx / 500.0f, -1.0f, 1.0f);
  const float tgtY = clampf((float)cmd_vy / 500.0f, -1.0f, 1.0f);
  const float tgtW = clampf((float)cmd_w_mrad / 1000.0f, -1.0f, 1.0f);  // stronger yaw
  // In-place yaw on this heavy mecanum needs a little roll — auto creep when pure tank.
  const bool pureYawCmd = fabsf(tgtW) > 0.20f && fabsf(tgtX) < 0.08f && fabsf(tgtY) < 0.08f;
  if (pureYawCmd) {
    tgtX = 0.28f;  // break static scrub so the chassis can yaw
  }
  rampX = slewToward(rampX, tgtX, RAMP_UP, RAMP_DOWN);
  rampY = tgtY;
  rampW = tgtW;

  if (!rampsActive() && !wheelRampsActive() &&
      abs(cmd_vx) < 30 && abs(cmd_vy) < 30 && abs(cmd_w_mrad) < 80) {
    coastMotors();
    for (int i = 0; i < 4; i++) { velInt[i] = 0.0f; emaTps[i] = 0.0f; }
    lastCorr = 0.0f;
    return;
  }

  float target[4];
  if (fabsf(tgtW) > 0.20f && fabsf(tgtY) < 0.08f) {
    // Explicit skid-steer tank: left pair vs right pair at full logical thrust.
    // +w → left reverse / right forward in wheel space (matches SIGN_* forward).
    const float s = (tgtW > 0.0f) ? 1.0f : -1.0f;
    target[0] = -s + rampX;  // FL
    target[1] = +s + rampX;  // FR
    target[2] = -s + rampX;  // RL
    target[3] = +s + rampX;  // RR
  } else {
    // Strafe / translate mix (textbook mecanum).
    target[0] = rampX - rampY - rampW;   // FL
    target[1] = rampX + rampY + rampW;   // FR
    target[2] = rampX + rampY - rampW;   // RL
    target[3] = rampX - rampY + rampW;   // RR
  }

  // Preserve mix ratios if a wheel exceeds full scale.
  float m = 0.0f;
  for (int i = 0; i < 4; i++) if (fabsf(target[i]) > m) m = fabsf(target[i]);
  if (m > 1.0f) {
    for (int i = 0; i < 4; i++) target[i] /= m;
  }

  float out[4];
  lastCorr = 0.0f;
  for (int i = 0; i < 4; i++) {
    float tps = (dt > 0.0f) ? (float)dTicks[i] / dt : 0.0f;
    emaTps[i] += EMA_ALPHA * (tps - emaTps[i]);
    float meas = emaTps[i] / calTps[i];          // normalized wheel speed

    if (fabsf(target[i]) < 0.008f) {
      out[i] = 0.0f;
      velInt[i] = 0.0f;
      continue;
    }

    float ff = target[i] * wheelScale[i];
    if (i == 1) {
      if (ff < 0.0f) ff *= frRevScale;
      else if (ff > 0.0f) ff *= frFwdScale;
    }

    if (!encTrusted[i] || (velKp <= 0.0f && velKi <= 0.0f)) {
      out[i] = ff;
      continue;
    }
    // Reset integrator on direction reversal to avoid windup kick.
    if ((target[i] > 0 && velInt[i] < -0.1f && meas < 0) ||
        (target[i] < 0 && velInt[i] > 0.1f && meas > 0)) {
      velInt[i] = 0.0f;
    }
    float err = target[i] - meas;
    velInt[i] = clampf(velInt[i] + err * dt * velKi, -VEL_INT_MAX, VEL_INT_MAX);
    float corr = clampf(velKp * err + velInt[i], -0.55f, 0.55f);
    if (fabsf(corr) > lastCorr) lastCorr = fabsf(corr);
    out[i] = clampf(ff + corr, -1.35f, 1.35f);
  }

  // Pure fwd/back: smooth per-wheel ramp. Crab/tank: snap wheels to max immediately.
  const bool snapTurn = (fabsf(tgtY) > 0.02f || fabsf(tgtW) > 0.02f);
  for (int i = 0; i < 4; i++) {
    out[i] = clampf(out[i], -1.0f, 1.0f);
    // Tank: push every driven wheel to full magnitude (don't leave mid PWM).
    if (snapTurn && fabsf(out[i]) > 0.05f) {
      out[i] = (out[i] > 0.0f) ? 1.0f : -1.0f;
    }
    if (snapTurn) rampOut[i] = out[i];
    else rampOut[i] = slewToward(rampOut[i], out[i], WHEEL_RAMP_UP, WHEEL_RAMP_DOWN);
  }

  driveFL(rampOut[0]);
  driveOneIdx(1, FR_PWM, FR_IN1, FR_IN2, SIGN_FR, rampOut[1]);
  driveRL(rampOut[2]);
  driveOneIdx(3, RR_PWM, RR_IN1, RR_IN2, SIGN_RR, rampOut[3]);
}

static void integrateOdom(const long dTicks[4]) {
  // FL encoder dead; FR/RL/RR determine the 3-DOF motion:
  //   fr = x + y + w,  rl = x + y - w,  rr = x - y + w
  //   => x = (rl + rr) / 2,  y = (fr - rr) / 2,  w = (fr - rl) / 2
  const float k = mmPerTick();
  const float mean = calMean();
  const float nFR = (float)dTicks[1] * mean / calTps[1];
  const float nRL = (float)dTicks[2] * mean / calTps[2];
  const float nRR = (float)dTicks[3] * mean / calTps[3];

  const float dx = 0.5f * (nRL + nRR) * k;                        // body forward
  const float dy = 0.5f * (nFR - nRR) * k;                        // body left
  const float dth = (nFR - nRL) * k / TRACK_WIDTH_MM;
  th += dth;
  while (th > PI) th -= 2.0f * PI;
  while (th < -PI) th += 2.0f * PI;
  const float c = cosf(th), s = sinf(th);
  x_mm += dx * c - dy * s;
  y_mm += dx * s + dy * c;
}

static void publishPose() {
  Serial.print(F("POS X=")); Serial.print(x_mm, 2);
  Serial.print(F(" Y=")); Serial.print(y_mm, 2);
  Serial.print(F(" Th=")); Serial.print(th, 2);
  Serial.print(F(" L=")); Serial.print((long)(normFR() + normRL()));
  Serial.print(F(" R=")); Serial.print((long)(2.0f * normRR()));
  Serial.print(F(" C=")); Serial.println(lastCorr, 2);
}

static void setCmd(int vx, int vy, int w_mrad) {
  hardBrake = false;
  brakeUntilMs = 0;
  cmd_vx = vx; cmd_vy = vy; cmd_w_mrad = w_mrad;
  lastCmdMs = millis();
}

static int nextInt(char **pp) {
  char *p = *pp;
  while (*p == ' ') p++;
  int v = atoi(p);
  while (*p && *p != ' ') p++;
  *pp = p;
  return v;
}

static void handleLine(char *line) {
  if (!line[0]) return;
  if (line[1] == '\0') {
    char c = line[0];
    if (c=='w'||c=='W') { setCmd( 500, 0, 0); return; }
    if (c=='s'||c=='S') { setCmd(-500, 0, 0); return; }
    if (c=='a'||c=='A') { setCmd(0,  500, 0); return; }
    if (c=='d'||c=='D') { setCmd(0, -500, 0); return; }
    if (c=='q'||c=='Q'||c=='z'||c=='Z') { setCmd(0, 0,  1500); return; }
    if (c=='e'||c=='E'||c=='c'||c=='C') { setCmd(0, 0, -1500); return; }
    if (c=='x'||c=='X'||c==' ') { stopHard(); return; }
  }
  if (!strncmp(line, "HARD_STOP", 9) || !strncmp(line, "BRAKE", 5)) {
    stopHard();
    Serial.println(F("HARD_STOP_OK"));
    return;
  }
  if (!strncmp(line, "STOP", 4)) { stopSoft(); return; }
  if (!strncmp(line, "PING", 4)) { Serial.println(F("PONG")); return; }
  if (!strncmp(line, "RESET_ODOM", 10)) {
    noInterrupts();
    encFL = encFR = encRL = encRR = 0;
    interrupts();
    for (int i = 0; i < 4; i++) prevTicks[i] = 0;
    x_mm = y_mm = th = 0;
    Serial.println(F("ODOM_OK"));
    return;
  }
  if (!strncmp(line, "ENC?", 4)) {
    Serial.print(F("ENC FL=")); Serial.print(encFL);
    Serial.print(F(" FR=")); Serial.print(encFR);
    Serial.print(F(" RL=")); Serial.print(encRL);
    Serial.print(F(" RR=")); Serial.println(encRR);
    return;
  }
  if (!strncmp(line, "SET_PIDV", 8)) {
    char *p = line + 8;
    int kp = nextInt(&p), ki = nextInt(&p);
    if (kp >= 0 && kp <= 3000 && ki >= 0 && ki <= 10000) {
      velKp = (float)kp / 1000.0f;
      velKi = (float)ki / 1000.0f;
      Serial.print(F("PIDV_OK ")); Serial.print(kp);
      Serial.print(F(" ")); Serial.println(ki);
    } else {
      Serial.println(F("PIDV_ERR"));
    }
    return;
  }
  if (!strncmp(line, "SET_CAL", 7)) {
    char *p = line + 7;
    int a = nextInt(&p), b = nextInt(&p), c = nextInt(&p), d = nextInt(&p);
    if (a > 50 && b > 50 && c > 50 && d > 50 &&
        a < 10000 && b < 10000 && c < 10000 && d < 10000) {
      calTps[0] = a; calTps[1] = b; calTps[2] = c; calTps[3] = d;
      Serial.print(F("CAL_OK ")); Serial.print(a); Serial.print(' ');
      Serial.print(b); Serial.print(' '); Serial.print(c); Serial.print(' ');
      Serial.println(d);
    } else {
      Serial.println(F("CAL_ERR"));
    }
    return;
  }
  if (!strncmp(line, "SET_POSE", 8)) {
    char *p = line + 8;
    while (*p == ' ') p++;
    x_mm = atof(p);
    while (*p && *p != ' ') p++;
    while (*p == ' ') p++;
    y_mm = atof(p);
    while (*p && *p != ' ') p++;
    while (*p == ' ') p++;
    th = atof(p);
    Serial.println(F("POSE_OK"));
    return;
  }
  if (!strncmp(line, "SET_FRB", 7)) {
    char *p = line + 7;
    int pct = nextInt(&p);
    if (pct >= 40 && pct <= 200) {
      frRevScale = (float)pct / 100.0f;
      Serial.print(F("FRB_OK ")); Serial.println(pct);
    } else {
      Serial.println(F("FRB_ERR"));
    }
    return;
  }
  if (!strncmp(line, "SET_FRF", 7)) {
    char *p = line + 7;
    int pct = nextInt(&p);
    if (pct >= 40 && pct <= 200) {
      frFwdScale = (float)pct / 100.0f;
      Serial.print(F("FRF_OK ")); Serial.println(pct);
    } else {
      Serial.println(F("FRF_ERR"));
    }
    return;
  }
  if (!strncmp(line, "SET_WSCALE", 10)) {
    char *p = line + 10;
    int a = nextInt(&p), b = nextInt(&p), c = nextInt(&p), d = nextInt(&p);
    if (a >= 40 && b >= 40 && c >= 40 && d >= 40 &&
        a <= 200 && b <= 200 && c <= 200 && d <= 200) {
      wheelScale[0] = (float)a / 100.0f;
      wheelScale[1] = (float)b / 100.0f;
      wheelScale[2] = (float)c / 100.0f;
      wheelScale[3] = (float)d / 100.0f;
      Serial.print(F("WSCALE_OK ")); Serial.print(a); Serial.print(' ');
      Serial.print(b); Serial.print(' '); Serial.print(c); Serial.print(' ');
      Serial.println(d);
    } else {
      Serial.println(F("WSCALE_ERR"));
    }
    return;
  }
  // TEST_WHEEL idx dir ms   idx: 0=FL 1=FR 2=RL 3=RR  dir: +1/-1
  if (!strncmp(line, "TEST_WHEEL", 10)) {
    char *p = line + 10;
    int idx = nextInt(&p), dir = nextInt(&p), ms = nextInt(&p);
    if (ms < 100) ms = 100;
    if (ms > 5000) ms = 5000;
    if (idx < 0 || idx > 3 || (dir != 1 && dir != -1)) {
      Serial.println(F("TEST_WHEEL_ERR"));
      return;
    }
    hardBrake = false;
    coastMotors();
    Serial.print(F("TEST_WHEEL ")); Serial.print(idx);
    Serial.print(F(" dir=")); Serial.println(dir);
    unsigned long until = millis() + (unsigned long)ms;
    float cmd = (dir > 0) ? 1.0f : -1.0f;
    while ((long)(millis() - until) < 0) {
      pollEncoders();
      if (idx == 0) driveFL(cmd);
      else if (idx == 2) driveRL(cmd);
      else {
        uint8_t pwms[4] = {FL_PWM, FR_PWM, RL_PWM, RR_PWM};
        uint8_t in1s[4] = {FL_IN1, FR_IN1, RL_IN1, RR_IN1};
        uint8_t in2s[4] = {FL_IN2, FR_IN2, RL_IN2, RR_IN2};
        int signs[4] = {SIGN_FL, SIGN_FR, SIGN_RL, SIGN_RR};
        driveOneIdx(idx, pwms[idx], in1s[idx], in2s[idx], signs[idx], cmd);
      }
    }
    coastMotors();
    for (int i = 0; i < 4; i++) lastDriveDir[i] = 0;
    Serial.println(F("TEST_WHEEL_OK"));
    lastCmdMs = millis();
    return;
  }
  if (!strncmp(line, "SET_ROBOT_VELOCITY", 18)) {
    char *p = line + 18;
    int a = nextInt(&p), b = 0, c = 0, n = 1;
    while (*p == ' ') p++;
    if (*p) {
      b = nextInt(&p); n = 2;
      while (*p == ' ') p++;
      if (*p) {
        if (strchr(p, '.')) c = (int)(atof(p) * 1000.0f);
        else c = nextInt(&p);
        n = 3;
      }
    }
    if (n >= 3) setCmd(a, b, c);
    else if (n == 2) setCmd(a, 0, b);
    else setCmd(a, 0, 0);
  }
}

static void pollSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen) { lineBuf[lineLen] = 0; handleLine(lineBuf); lineLen = 0; }
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    } else {
      lineLen = 0;
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(ENC_FL_A, INPUT_PULLUP); pinMode(ENC_FL_B, INPUT_PULLUP);
  pinMode(ENC_FR_A, INPUT_PULLUP); pinMode(ENC_FR_B, INPUT_PULLUP);
  pinMode(ENC_RL_A, INPUT_PULLUP); pinMode(ENC_RL_B, INPUT_PULLUP);
  pinMode(ENC_RR_A, INPUT_PULLUP); pinMode(ENC_RR_B, INPUT_PULLUP);
  prevFLA = digitalRead(ENC_FL_A);
  prevFRA = digitalRead(ENC_FR_A);
  prevRLA = digitalRead(ENC_RL_A);
  prevRRA = digitalRead(ENC_RR_A);
  pinMode(FL_IN1, OUTPUT); pinMode(FL_IN2, OUTPUT); pinMode(FL_PWM, OUTPUT);
  pinMode(FR_IN1, OUTPUT); pinMode(FR_IN2, OUTPUT); pinMode(FR_PWM, OUTPUT);
  pinMode(RL_IN1, OUTPUT); pinMode(RL_IN2, OUTPUT); pinMode(RL_PWM, OUTPUT);
  pinMode(RR_IN1, OUTPUT); pinMode(RR_IN2, OUTPUT); pinMode(RR_PWM, OUTPUT);
  stopHard();
  coastMotors();
  hardBrake = false;
  brakeUntilMs = 0;
  lastCmdMs = millis();
  Serial.println(F("READY mecanum-velpid"));
}

void loop() {
  static unsigned long lastPos = 0;
  static unsigned long lastCtrl = 0;

  pollEncoders();
  pollSerial();
  pollEncoders();

  unsigned long now = millis();
  if ((cmd_vx || cmd_vy || cmd_w_mrad) && (now - lastCmdMs > CMD_TIMEOUT_MS))
    stopHard();

  if (now - lastCtrl >= CTRL_PERIOD_MS) {
    float dt = (now - lastCtrl) * 0.001f;
    if (dt > 0.12f) dt = 0.12f;
    lastCtrl = now;

    long cur[4] = {encFL, encFR, encRL, encRR};
    long dTicks[4];
    for (int i = 0; i < 4; i++) {
      dTicks[i] = cur[i] - prevTicks[i];
      prevTicks[i] = cur[i];
    }

    integrateOdom(dTicks);
    // Keep applying while ramping/coasting/braking so soft stop works.
    if (cmd_vx || cmd_vy || cmd_w_mrad || rampsActive() || wheelRampsActive() || hardBrake) {
      applyMotors(dt, dTicks);
    }
  }

  if (now - lastPos >= POS_PERIOD_MS) {
    lastPos = now;
    publishPose();
  }
}
