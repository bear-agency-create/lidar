/*
  MecanumTeleopBridge — PID straight (rate-based, anti-runaway)

  Starts straight then grows left curve = cumulative error / wrong feedback.
  Fix: PID on per-cycle tick rate only, leaky I, limited corr, correct sign.
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

static const int SIGN_FL = +1, SIGN_FR = +1, SIGN_RL = +1, SIGN_RR = +1;
static const int ENC_SIGN_FL = +1, ENC_SIGN_FR = +1, ENC_SIGN_RL = +1, ENC_SIGN_RR = -1;

// Between "1 m OK" and overcorrection (left side was sticking out).
static float TRIM_L = 1.36f;
static float TRIM_R = 0.52f;
static float BIAS_CORR = 20.0f;

static const int BASE_PWM = 220;
static const int MIN_PWM = 80;
static const int MAX_PWM = 255;

static const float WHEEL_DIAMETER_MM = 65.0f;
static const float TRACK_WIDTH_MM = 560.0f;
static const long  TICKS_PER_REV = 20;

// PID disabled (kept for later tuning via SET_TRIM only)
static const float KP = 0.0f;
static const float KI = 0.0f;
static const float KD = 0.0f;
static const float I_LEAK = 0.90f;
static const float I_LIMIT = 20.0f;
static const float OUT_LIMIT = 40.0f;
static const float DEADBAND = 1.0f;
static const float SLEW_PWM = 5.0f;
static const float FILT_A = 0.35f;

static const unsigned long CMD_TIMEOUT_MS = 1200;
static const unsigned long POS_PERIOD_MS = 100;
static const unsigned long CTRL_PERIOD_MS = 30;
static const unsigned long RAMP_MS = 400;

static int cmd_vx = 0, cmd_vy = 0, cmd_w_mrad = 0;
static unsigned long lastCmdMs = 0;
static unsigned long moveStartMs = 0;
static float x_mm = 0, y_mm = 0, th = 0;
static char lineBuf[120];
static uint8_t lineLen = 0;

volatile long encFL = 0, encFR = 0, encRL = 0, encRR = 0;
static uint8_t prevFLA, prevFRA, prevRLA, prevRRA;

static float pid_i = 0, pid_prev_err = 0, pid_filt = 0, corr_applied = 0;
static bool moving_straight = false;

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

// Diagonal pair — less sensitive to one weak channel (FR)
static long readLeft()  { return encFL + encRL; }
static long readRight() { return encFR + encRR; }
static long readPidL()  { return encFL; }   // front-left only
static long readPidR()  { return encRR; }   // rear-right only (strongest right signal)

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

static void setWheels(int fl, int fr, int rl, int rr, int pwmL, int pwmR) {
  motor(FL_PWM, FL_IN1, FL_IN2, fl, SIGN_FL, pwmL);
  motor(FR_PWM, FR_IN1, FR_IN2, fr, SIGN_FR, pwmR);
  motor(RL_PWM, RL_IN1, RL_IN2, rl, SIGN_RL, pwmL);
  motor(RR_PWM, RR_IN1, RR_IN2, rr, SIGN_RR, pwmR);
}

static void resetPid() {
  pid_i = 0;
  pid_prev_err = 0;
  pid_filt = 0;
  corr_applied = 0;
  moving_straight = false;
}

static void stopMotors() {
  setWheels(0, 0, 0, 0, 0, 0);
  cmd_vx = cmd_vy = cmd_w_mrad = 0;
  resetPid();
}

static bool isStraightCmd() {
  const int ax = abs(cmd_vx);
  const int ay = abs(cmd_vy);
  const int aw = abs(cmd_w_mrad);
  return (ax >= 30 && ax >= ay && ax >= aw / 3);
}

static float runStraightPid(float dt, long dPidL, long dPidR) {
  if (!isStraightCmd() || dt < 0.001f) {
    resetPid();
    return 0.0f;
  }
  if (!moving_straight) {
    moving_straight = true;
    moveStartMs = millis();
    pid_i = 0;
    pid_prev_err = 0;
    pid_filt = 0;
    corr_applied = 0;
  }

  // Right faster than left → positive (physical left turn)
  float e = (float)(dPidR - dPidL);
  if (fabsf(e) < DEADBAND) e = 0.0f;

  pid_i = pid_i * I_LEAK + e * dt;
  pid_i = clampf(pid_i, -I_LIMIT, I_LIMIT);

  float deriv = (e - pid_prev_err) / dt;
  pid_prev_err = e;

  float raw = KP * e + KI * pid_i + KD * deriv;
  raw = clampf(raw, -OUT_LIMIT, OUT_LIMIT);
  pid_filt += FILT_A * (raw - pid_filt);

  float delta = clampf(pid_filt - corr_applied, -SLEW_PWM, SLEW_PWM);
  corr_applied += delta;

  float corr = corr_applied;
  if (cmd_vx < 0) corr = -corr;
  return corr;
}

static float rampScale() {
  if (!moving_straight) return 0.55f;
  unsigned long age = millis() - moveStartMs;
  if (age >= RAMP_MS) return 1.0f;
  return 0.55f + 0.45f * ((float)age / (float)RAMP_MS);
}

static void sidePwm(int *outL, int *outR, float corr) {
  float scale = isStraightCmd() ? rampScale() : 1.0f;
  float base = (float)BASE_PWM * scale;
  float bias = isStraightCmd() ? BIAS_CORR : 0.0f;
  // +corr/+bias → more left, less right
  *outL = clampPwm((int)(base * TRIM_L + corr + bias + 0.5f));
  *outR = clampPwm((int)(base * TRIM_R - corr - bias + 0.5f));
}

static void applyVelocityCommand(float corr) {
  const int ax = abs(cmd_vx);
  const int ay = abs(cmd_vy);
  const int aw = abs(cmd_w_mrad);
  int pwmL = 0, pwmR = 0;

  if (ax < 30 && ay < 30 && aw < 80) {
    stopMotors();
    return;
  }

  if (ax >= ay && ax >= aw / 3) {
    sidePwm(&pwmL, &pwmR, corr);
    int d = (cmd_vx > 0) ? +1 : -1;
    setWheels(d, d, d, d, pwmL, pwmR);
    return;
  }
  resetPid();
  sidePwm(&pwmL, &pwmR, 0);
  if (ay >= ax && ay >= aw / 3) {
    int s = (cmd_vy > 0) ? +1 : -1;
    setWheels(-s, +s, +s, -s, pwmL, pwmR);
    return;
  }
  int y = (cmd_w_mrad > 0) ? +1 : -1;
  setWheels(-y, +y, -y, +y, pwmL, pwmR);
}

static void integrateOdom(float dt, long dL, long dR) {
  // Use FL+RR only (cleaner) via passed dL/dR sums already.
  const float dl = 0.5f * dL * mmPerTick();
  const float dr = 0.5f * dR * mmPerTick();
  float ds = 0.5f * (dl + dr);
  float dth = (dr - dl) / TRACK_WIDTH_MM;

  // Straight teleop: encoder yaw is noisy (trim + unequal wheels) and
  // makes the map spin. Keep heading, only advance distance.
  const int ax = abs(cmd_vx);
  const int ay = abs(cmd_vy);
  const int aw = abs(cmd_w_mrad);
  if (ax >= 30 && ax >= ay && aw < 80) {
    dth *= 0.05f;  // almost ignore yaw from encoders while going straight
  } else if (ay >= 30 && ay >= ax && aw < 80) {
    dth *= 0.15f;
  }

  th += dth;
  while (th > PI) th -= 2.0f * PI;
  while (th < -PI) th += 2.0f * PI;
  x_mm += ds * cosf(th);
  y_mm += ds * sinf(th);
  if (abs(cmd_vy) > 30) {
    const float v = (float)cmd_vy;
    x_mm += (-sinf(th) * v * dt);
    y_mm += ( cosf(th) * v * dt);
  }
}

static void publishPose() {
  Serial.print(F("POS X=")); Serial.print(x_mm, 2);
  Serial.print(F(" Y=")); Serial.print(y_mm, 2);
  Serial.print(F(" Th=")); Serial.print(th, 2);
  Serial.print(F(" L=")); Serial.print(readLeft());
  Serial.print(F(" R=")); Serial.print(readRight());
  Serial.print(F(" C=")); Serial.println(corr_applied, 1);
}

static void publishEnc() {
  Serial.print(F("ENC FL=")); Serial.print(encFL);
  Serial.print(F(" FR=")); Serial.print(encFR);
  Serial.print(F(" RL=")); Serial.print(encRL);
  Serial.print(F(" RR=")); Serial.println(encRR);
}

static void setCmd(int vx, int vy, int w_mrad) {
  bool was = isStraightCmd();
  cmd_vx = vx; cmd_vy = vy; cmd_w_mrad = w_mrad;
  lastCmdMs = millis();
  if (!was && isStraightCmd()) resetPid();
  if (!isStraightCmd()) resetPid();
  if (Serial.availableForWrite() > 20) {
    Serial.print(F("ACK "));
    Serial.print(vx); Serial.print(' ');
    Serial.print(vy); Serial.print(' ');
    Serial.println(w_mrad);
  }
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
    if (c=='q'||c=='Q') { setCmd(0, 0,  1500); return; }
    if (c=='e'||c=='E') { setCmd(0, 0, -1500); return; }
    if (c=='x'||c=='X'||c==' ') { stopMotors(); return; }
  }
  if (!strncmp(line, "STOP", 4)) { stopMotors(); return; }
  if (!strncmp(line, "PING", 4)) { Serial.println(F("PONG")); return; }
  if (!strncmp(line, "ENC?", 4)) { publishEnc(); return; }
  if (!strncmp(line, "SET_TRIM", 8)) {
    char *p = line + 8;
    int a = nextInt(&p), b = nextInt(&p);
    if (a > 50 && a <= 130) TRIM_L = a / 100.0f;
    if (b > 50 && b <= 130) TRIM_R = b / 100.0f;
    Serial.print(F("TRIM L=")); Serial.print(TRIM_L, 2);
    Serial.print(F(" R=")); Serial.println(TRIM_R, 2);
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
    } else if (lineLen < sizeof(lineBuf) - 1) lineBuf[lineLen++] = c;
    else lineLen = 0;
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
  Serial.println(F("READY pid-rate"));
}

void loop() {
  static unsigned long lastPos = 0;
  static unsigned long lastCtrl = 0;
  static long prevL = 0, prevR = 0, prevPidL = 0, prevPidR = 0;

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

    long l = readLeft(), r = readRight();
    long dL = l - prevL, dR = r - prevR;
    prevL = l; prevR = r;

    long pL = readPidL(), pR = readPidR();
    long dPidL = pL - prevPidL, dPidR = pR - prevPidR;
    prevPidL = pL; prevPidR = pR;

    if (cmd_vx || cmd_vy || cmd_w_mrad) {
      integrateOdom(dt, dL, dR);
      float corr = runStraightPid(dt, dPidL, dPidR);
      applyVelocityCommand(corr);
    }
  }

  if (now - lastPos >= POS_PERIOD_MS) {
    lastPos = now;
    publishPose();
  }
}
