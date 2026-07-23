/*
  MegaRobotBridge — Arduino Mega for ROS2 robot_driver
  =================================================================
  Protocol (115200 8N1):

  Pi → Mega:
    SET_ROBOT_VELOCITY <vx_mm_s> <vy_mm_s> <w_rad_s>   // mecanum (3 args)
    SET_ROBOT_VELOCITY <vx_mm_s> <w_rad_s>              // legacy tank (2 args)
    SET_POSE <x_mm> <y_mm> <th_rad>
    STOP

  Mega → Pi:
    POS X=<x_mm> Y=<y_mm> Th=<th_rad>

  Mecanum 4 motors (FL/FR/RL/RR). Each needs its own PWM:
    FL PWM=5  IN1=8  IN2=9
    FR PWM=6  IN1=10 IN2=11
    RL PWM=44 IN1=12 IN2=13   ← if was shared with FL, move Enable to D44
    RR PWM=45 IN1=A0 IN2=A1   ← if was shared with FR, move Enable to D45

  Encoders (approx odom): left A=D2 B=D4, right A=D3 B=D7
*/

#include <math.h>
#include <string.h>

static const float WHEEL_DIAMETER_MM = 65.0f;
static const float TRACK_WIDTH_MM    = 560.0f;  // robot width (y)
static const float WHEELBASE_MM      = 820.0f;  // robot length (x)
static const long  TICKS_PER_REV     = 20;
static const float CONTROL_HZ        = 50.0f;

static const uint8_t ENC_L_A = 2;
static const uint8_t ENC_L_B = 4;
static const uint8_t ENC_R_A = 3;
static const uint8_t ENC_R_B = 7;

static const uint8_t FL_PWM = 5;
static const uint8_t FL_IN1 = 8;
static const uint8_t FL_IN2 = 9;

static const uint8_t FR_PWM = 6;
static const uint8_t FR_IN1 = 10;
static const uint8_t FR_IN2 = 11;

static const uint8_t RL_PWM = 44;
static const uint8_t RL_IN1 = 12;
static const uint8_t RL_IN2 = 13;

static const uint8_t RR_PWM = 45;
static const uint8_t RR_IN1 = A0;
static const uint8_t RR_IN2 = A1;

static const int MIN_PWM = 70;
static const int MAX_PWM = 220;
static const float KP_V = 0.85f;

volatile long encLeftTicks  = 0;
volatile long encRightTicks = 0;

static float x_mm = 0.0f;
static float y_mm = 0.0f;
static float th   = 0.0f;

static float cmd_vx = 0.0f;
static float cmd_vy = 0.0f;
static float cmd_w  = 0.0f;

static char lineBuf[96];
static uint8_t lineLen = 0;

static float mmPerTick() {
  return (PI * WHEEL_DIAMETER_MM) / (float)TICKS_PER_REV;
}

static void encLeftIsr() {
  const bool a = digitalRead(ENC_L_A);
  const bool b = digitalRead(ENC_L_B);
  if (a == b) encLeftTicks++;
  else encLeftTicks--;
}

static void encRightIsr() {
  const bool a = digitalRead(ENC_R_A);
  const bool b = digitalRead(ENC_R_B);
  if (a == b) encRightTicks--;
  else encRightTicks++;
}

static long readEncLeft() {
  noInterrupts();
  const long v = encLeftTicks;
  interrupts();
  return v;
}

static long readEncRight() {
  noInterrupts();
  const long v = encRightTicks;
  interrupts();
  return v;
}

static int clampPwm(int v) {
  if (v > 0 && v < MIN_PWM) v = MIN_PWM;
  if (v < 0 && v > -MIN_PWM) v = -MIN_PWM;
  if (v > MAX_PWM) v = MAX_PWM;
  if (v < -MAX_PWM) v = -MAX_PWM;
  return v;
}

static void writeMotor(uint8_t pwmPin, uint8_t in1, uint8_t in2, int speed) {
  const int mag = abs(speed);
  if (speed > 0) {
    digitalWrite(in1, HIGH);
    digitalWrite(in2, LOW);
  } else if (speed < 0) {
    digitalWrite(in1, LOW);
    digitalWrite(in2, HIGH);
  } else {
    digitalWrite(in1, LOW);
    digitalWrite(in2, LOW);
  }
  analogWrite(pwmPin, mag);
}

static void setFour(int fl, int fr, int rl, int rr) {
  writeMotor(FL_PWM, FL_IN1, FL_IN2, clampPwm(fl));
  writeMotor(FR_PWM, FR_IN1, FR_IN2, clampPwm(fr));
  writeMotor(RL_PWM, RL_IN1, RL_IN2, clampPwm(rl));
  writeMotor(RR_PWM, RR_IN1, RR_IN2, clampPwm(rr));
}

static void stopMotors() {
  setFour(0, 0, 0, 0);
}

static void applyVelocityCommand() {
  // Mecanum inverse kinematics (mm/s, rad/s)
  const float lx = WHEELBASE_MM * 0.5f;
  const float ly = TRACK_WIDTH_MM * 0.5f;
  const float r = lx + ly;
  const float fl = cmd_vx - cmd_vy - r * cmd_w;
  const float fr = cmd_vx + cmd_vy + r * cmd_w;
  const float rl = cmd_vx + cmd_vy - r * cmd_w;
  const float rr = cmd_vx - cmd_vy + r * cmd_w;
  setFour((int)(fl * KP_V), (int)(fr * KP_V), (int)(rl * KP_V), (int)(rr * KP_V));
}

static void integrateOdom(float dt) {
  static long prevL = 0;
  static long prevR = 0;
  const long l = readEncLeft();
  const long r = readEncRight();
  const float dl = (l - prevL) * mmPerTick();
  const float dr = (r - prevR) * mmPerTick();
  prevL = l;
  prevR = r;

  // Approx planar odom from left/right encoders (strafe poorly observed)
  const float ds = 0.5f * (dl + dr);
  float dth = (dr - dl) / TRACK_WIDTH_MM;
  th += dth;
  while (th > PI) th -= 2.0f * PI;
  while (th < -PI) th += 2.0f * PI;
  x_mm += ds * cosf(th);
  y_mm += ds * sinf(th);
  // open-loop strafe assist when encoders don't see vy
  if (fabsf(cmd_vy) > 1.0f) {
    x_mm += (-sinf(th) * cmd_vy * dt);
    y_mm += ( cosf(th) * cmd_vy * dt);
  }
  (void)dt;
}

static void publishPose() {
  Serial.print(F("POS X="));
  Serial.print(x_mm, 2);
  Serial.print(F(" Y="));
  Serial.print(y_mm, 2);
  Serial.print(F(" Th="));
  Serial.println(th, 2);
}

static void handleLine(char *line) {
  if (strncmp(line, "SET_ROBOT_VELOCITY", 18) == 0) {
    float a = 0.0f, b = 0.0f, c = 0.0f;
    const int n = sscanf(line + 18, "%f %f %f", &a, &b, &c);
    if (n >= 3) {
      cmd_vx = a;
      cmd_vy = b;
      cmd_w = c;
    } else if (n == 2) {
      // legacy: lin, ang
      cmd_vx = a;
      cmd_vy = 0.0f;
      cmd_w = b;
    } else if (n == 1) {
      cmd_vx = a;
      cmd_vy = 0.0f;
      cmd_w = 0.0f;
    }
    applyVelocityCommand();
  } else if (strncmp(line, "SET_POSE", 8) == 0) {
    float nx = 0.0f, ny = 0.0f, nth = 0.0f;
    if (sscanf(line + 8, "%f %f %f", &nx, &ny, &nth) >= 3) {
      x_mm = nx;
      y_mm = ny;
      th = nth;
    }
  } else if (strncmp(line, "STOP", 4) == 0) {
    cmd_vx = 0.0f;
    cmd_vy = 0.0f;
    cmd_w = 0.0f;
    stopMotors();
  }
}

static void pollSerial() {
  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen > 0) {
        lineBuf[lineLen] = '\0';
        handleLine(lineBuf);
        lineLen = 0;
      }
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    } else {
      lineLen = 0;
    }
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(ENC_L_A, INPUT_PULLUP);
  pinMode(ENC_L_B, INPUT_PULLUP);
  pinMode(ENC_R_A, INPUT_PULLUP);
  pinMode(ENC_R_B, INPUT_PULLUP);

  pinMode(FL_IN1, OUTPUT);
  pinMode(FL_IN2, OUTPUT);
  pinMode(FR_IN1, OUTPUT);
  pinMode(FR_IN2, OUTPUT);
  pinMode(RL_IN1, OUTPUT);
  pinMode(RL_IN2, OUTPUT);
  pinMode(RR_IN1, OUTPUT);
  pinMode(RR_IN2, OUTPUT);
  pinMode(FL_PWM, OUTPUT);
  pinMode(FR_PWM, OUTPUT);
  pinMode(RL_PWM, OUTPUT);
  pinMode(RR_PWM, OUTPUT);

  stopMotors();
  attachInterrupt(digitalPinToInterrupt(ENC_L_A), encLeftIsr, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_R_A), encRightIsr, CHANGE);

  Serial.println(F("MegaRobotBridge mecanum ready"));
}

void loop() {
  static unsigned long lastMs = 0;
  const unsigned long now = millis();
  const float dt = 1.0f / CONTROL_HZ;

  pollSerial();

  if (now - lastMs >= (unsigned long)(1000.0f / CONTROL_HZ)) {
    lastMs = now;
    integrateOdom(dt);
    applyVelocityCommand();
    publishPose();
  }
}
