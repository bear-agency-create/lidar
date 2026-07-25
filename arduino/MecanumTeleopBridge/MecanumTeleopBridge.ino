/*
  MecanumTeleopBridge — mecanum drive with per-wheel velocity alignment

  Motions: forward / back (vx), strafe left / right (vy), rotate (w).

  Alignment: encoders have very different resolutions per wheel
  (calibrated 2026-07-24: straight rolling gives FL~572, FR~336,
  RL~1960, RR~1423 ticks/s at mix 1.0). FL/RL/RR encoders are
  mutually consistent; the FR encoder intermittently drops 15-25% of
  ticks, so closing a loop on it overdrives that wheel and twists the
  chassis. Therefore: FL, RL and RR run per-wheel PI velocity loops
  (tick rate normalized by the wheel's own full-scale rate), FR runs
  feedforward-only, and odometry is solved from the three reliable
  wheels (3 wheels fully determine the 3-DOF mecanum chassis motion).

  Serial protocol (115200, \n terminated):
    SET_ROBOT_VELOCITY vx vy w   vx/vy ~500 = full, w ~1500 = full
    w/s/a/d                      fwd / back / strafe L / strafe R
    q/e (z/c)                    rotate CCW / CW
    x or space or STOP           stop
    PING                         -> PONG
    RESET_ODOM                   zero encoders + pose -> ODOM_OK
    SET_POSE x_mm y_mm th        override pose -> POSE_OK
    ENC?                         raw per-wheel encoder counts
    SET_PIDV kp ki               velocity-loop gains x1000 (default 500 2500)
    SET_CAL fl fr rl rr          full-scale ticks/s per wheel
    SET_FRB pct                  FR reverse-direction scale in percent

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

static const int SIGN_FL = -1, SIGN_FR = +1, SIGN_RL = -1, SIGN_RR = +1;
static const int ENC_SIGN_FL = -1, ENC_SIGN_FR = +1, ENC_SIGN_RL = -1, ENC_SIGN_RR = -1;

static const int BASE_PWM = 200;
static const int MIN_PWM = 80;
static const int MAX_PWM = 255;

static const float WHEEL_DIAMETER_MM = 65.0f;
static const float TRACK_WIDTH_MM = 560.0f;
static const long  TICKS_PER_REV = 20;

static const unsigned long CMD_TIMEOUT_MS = 1200;
static const unsigned long POS_PERIOD_MS = 80;
static const unsigned long CTRL_PERIOD_MS = 25;

// Full-scale ticks/s per wheel at mix 1.0 (PWM ~200), measured on floor.
static float calTps[4] = {572.0f, 336.0f, 1960.0f, 1423.0f};   // FL FR RL RR

// Wheels with trustworthy encoders (index: 0=FL 1=FR 2=RL 3=RR)
static const bool encTrusted[4] = {true, false, true, true};

// FR runs feedforward-only; its reverse direction needs a scale fix
// (lidar-tuned 2026-07-24, SET_FRB sweep minimum around 108%).
static float frRevScale = 1.08f;

// Per-wheel velocity PI (normalized units)
static float velKp = 0.500f;
static float velKi = 2.500f;
static const float VEL_INT_MAX = 0.35f;
static const float EMA_ALPHA = 0.30f;
static const float RAMP_STEP = 0.09f;      // max mix change per control tick

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
static float emaTps[4] = {0, 0, 0, 0};
static float velInt[4] = {0, 0, 0, 0};
static float lastCorr = 0.0f;   // max |PI correction| for telemetry

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
static float normRL() { return (float)encRL * calMean() / calTps[2]; }
static float normRR() { return (float)encRR * calMean() / calTps[3]; }

static int clampPwm(int v) {
  if (v < 0) v = 0;
  if (v > MAX_PWM) v = MAX_PWM;
  if (v > 0 && v < MIN_PWM) v = MIN_PWM;
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

static void driveOne(uint8_t pwm, uint8_t in1, uint8_t in2, int sign, float v) {
  int dir = 0;
  if (v > 0.04f) dir = +1;
  else if (v < -0.04f) dir = -1;
  int spd = (dir == 0) ? 0 : clampPwm((int)(fabsf(v) * (float)BASE_PWM + 0.5f));
  motor(pwm, in1, in2, dir, sign, spd);
}

static void resetControl() {
  rampX = rampY = rampW = 0.0f;
  for (int i = 0; i < 4; i++) { velInt[i] = 0.0f; emaTps[i] = 0.0f; }
  lastCorr = 0.0f;
}

static void stopMotors() {
  motor(FL_PWM, FL_IN1, FL_IN2, 0, SIGN_FL, 0);
  motor(FR_PWM, FR_IN1, FR_IN2, 0, SIGN_FR, 0);
  motor(RL_PWM, RL_IN1, RL_IN2, 0, SIGN_RL, 0);
  motor(RR_PWM, RR_IN1, RR_IN2, 0, SIGN_RR, 0);
  cmd_vx = cmd_vy = cmd_w_mrad = 0;
  resetControl();
}

static float slew(float current, float target) {
  float d = target - current;
  if (d > RAMP_STEP) d = RAMP_STEP;
  if (d < -RAMP_STEP) d = -RAMP_STEP;
  return current + d;
}

static void applyMotors(float dt, const long dTicks[4]) {
  const int ax = abs(cmd_vx);
  const int ay = abs(cmd_vy);
  const int aw = abs(cmd_w_mrad);
  if (ax < 30 && ay < 30 && aw < 80) {
    stopMotors();
    return;
  }

  rampX = slew(rampX, clampf((float)cmd_vx / 500.0f, -1.0f, 1.0f));
  rampY = slew(rampY, clampf((float)cmd_vy / 500.0f, -1.0f, 1.0f));
  rampW = slew(rampW, clampf((float)cmd_w_mrad / 1500.0f, -1.0f, 1.0f));

  float target[4];
  target[0] = rampX - rampY - rampW;   // FL
  target[1] = rampX + rampY + rampW;   // FR
  target[2] = rampX + rampY - rampW;   // RL
  target[3] = rampX - rampY + rampW;   // RR

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

    if (fabsf(target[i]) < 0.04f) {
      out[i] = 0.0f;
      velInt[i] = 0.0f;
      continue;
    }
    if (!encTrusted[i]) {
      out[i] = target[i];   // feedforward only
      if (i == 1 && out[i] < 0.0f) out[i] *= frRevScale;
      continue;
    }
    // Reset integrator on direction reversal to avoid windup kick.
    if ((target[i] > 0 && velInt[i] < -0.1f && meas < 0) ||
        (target[i] < 0 && velInt[i] > 0.1f && meas > 0)) {
      velInt[i] = 0.0f;
    }
    float err = target[i] - meas;
    velInt[i] = clampf(velInt[i] + err * dt * velKi, -VEL_INT_MAX, VEL_INT_MAX);
    float corr = clampf(velKp * err + velInt[i], -0.45f, 0.45f);
    if (fabsf(corr) > lastCorr) lastCorr = fabsf(corr);
    out[i] = clampf(target[i] + corr, -1.27f, 1.27f);
  }

  driveOne(FL_PWM, FL_IN1, FL_IN2, SIGN_FL, out[0]);
  driveOne(FR_PWM, FR_IN1, FR_IN2, SIGN_FR, out[1]);
  driveOne(RL_PWM, RL_IN1, RL_IN2, SIGN_RL, out[2]);
  driveOne(RR_PWM, RR_IN1, RR_IN2, SIGN_RR, out[3]);
}

static void integrateOdom(const long dTicks[4]) {
  // FR encoder drops ticks; FL/RL/RR alone determine the 3-DOF motion:
  //   fl = x - y - w,  rl = x + y - w,  rr = x - y + w
  //   => x = (rl + rr) / 2,  y = (rl - fl) / 2,  w = (rr - fl) / 2
  const float k = mmPerTick();
  const float mean = calMean();
  const float nFL = (float)dTicks[0] * mean / calTps[0];
  const float nRL = (float)dTicks[2] * mean / calTps[2];
  const float nRR = (float)dTicks[3] * mean / calTps[3];

  const float dx = 0.5f * (nRL + nRR) * k;                        // body forward
  const float dy = 0.5f * (nRL - nFL) * k;                        // body left
  const float dth = (nRR - nFL) * k / TRACK_WIDTH_MM;
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
  Serial.print(F(" L=")); Serial.print((long)(normFL() + normRL()));
  Serial.print(F(" R=")); Serial.print((long)(2.0f * normRR()));
  Serial.print(F(" C=")); Serial.println(lastCorr, 2);
}

static void setCmd(int vx, int vy, int w_mrad) {
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
    if (c=='x'||c=='X'||c==' ') { stopMotors(); return; }
  }
  if (!strncmp(line, "STOP", 4)) { stopMotors(); return; }
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
  stopMotors();
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
    stopMotors();

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
    if (cmd_vx || cmd_vy || cmd_w_mrad) {
      applyMotors(dt, dTicks);
    }
  }

  if (now - lastPos >= POS_PERIOD_MS) {
    lastPos = now;
    publishPose();
  }
}
