/*
  MotorSmokeTest v2 — find which Enable pins drive motors
  Phases print to Serial; watch which wheels move.
*/

static const uint8_t FL_IN1 = 8,  FL_IN2 = 9;
static const uint8_t FR_IN1 = 10, FR_IN2 = 11;
static const uint8_t RL_IN1 = 12, RL_IN2 = 13;
static const uint8_t RR_IN1 = A0, RR_IN2 = A1;

static const uint8_t EN_PINS[] = {5, 6, 44, 45};

static void oneDir(uint8_t a, uint8_t b, int dir) {
  if (dir > 0) { digitalWrite(a, HIGH); digitalWrite(b, LOW); }
  else if (dir < 0) { digitalWrite(a, LOW); digitalWrite(b, HIGH); }
  else { digitalWrite(a, LOW); digitalWrite(b, LOW); }
}

static void dirs(int dir) {
  oneDir(FL_IN1, FL_IN2, dir);
  oneDir(FR_IN1, FR_IN2, dir);
  oneDir(RL_IN1, RL_IN2, dir);
  oneDir(RR_IN1, RR_IN2, dir);
}

static void enablesOff() {
  for (uint8_t i = 0; i < 4; i++) analogWrite(EN_PINS[i], 0);
}

static void enablesOnMask(uint8_t mask) {
  enablesOff();
  for (uint8_t i = 0; i < 4; i++) {
    if (mask & (1 << i)) analogWrite(EN_PINS[i], 255);
  }
}

static void hold(int dir, uint8_t mask, const __FlashStringHelper *label, unsigned ms) {
  Serial.println(label);
  dirs(dir);
  enablesOnMask(mask);
  delay(ms);
  enablesOff();
  dirs(0);
  delay(500);
}

void setup() {
  Serial.begin(115200);
  pinMode(FL_IN1, OUTPUT); pinMode(FL_IN2, OUTPUT);
  pinMode(FR_IN1, OUTPUT); pinMode(FR_IN2, OUTPUT);
  pinMode(RL_IN1, OUTPUT); pinMode(RL_IN2, OUTPUT);
  pinMode(RR_IN1, OUTPUT); pinMode(RR_IN2, OUTPUT);
  for (uint8_t i = 0; i < 4; i++) pinMode(EN_PINS[i], OUTPUT);
  enablesOff();
  dirs(0);

  Serial.println(F("SMOKE v2 — watch wheels each phase"));
  // bits: 0=D5 1=D6 2=D44 3=D45
  hold(+1, 0b0011, F("A FWD En D5+D6"), 3500);
  hold(+1, 0b1100, F("B FWD En D44+D45"), 3500);
  hold(+1, 0b1111, F("C FWD En ALL"), 3500);
  hold(+1, 0b0001, F("D FWD En D5 only"), 2500);
  hold(+1, 0b0010, F("E FWD En D6 only"), 2500);
  hold(-1, 0b1111, F("F REV En ALL"), 3500);
  Serial.println(F("SMOKE v2 done"));
}

void loop() {
  if (!Serial.available()) return;
  char c = Serial.read();
  if (c == 'f') { dirs(+1); enablesOnMask(0b1111); Serial.println(F("FWD")); }
  else if (c == 'r') { dirs(-1); enablesOnMask(0b1111); Serial.println(F("REV")); }
  else if (c == 'x' || c == ' ') { dirs(0); enablesOff(); Serial.println(F("STOP")); }
}
