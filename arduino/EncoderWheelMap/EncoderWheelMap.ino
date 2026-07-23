/*
  EncoderWheelMap — spin each motor alone, report which of 46..53 flip.
*/
static const uint8_t FL_PWM = 8,  FL_IN1 = 9,  FL_IN2 = 10;
static const uint8_t FR_PWM = 7,  FR_IN1 = 5,  FR_IN2 = 6;
static const uint8_t RL_PWM = 13, RL_IN1 = 11, RL_IN2 = 12;
static const uint8_t RR_PWM = 2,  RR_IN1 = 3,  RR_IN2 = 4;

static const uint8_t EPINS[8] = {46,47,48,49,50,51,52,53};
static uint8_t prev[8];
static uint16_t flips[8];

static void allOff() {
  digitalWrite(FL_IN1,0); digitalWrite(FL_IN2,0); analogWrite(FL_PWM,0);
  digitalWrite(FR_IN1,0); digitalWrite(FR_IN2,0); analogWrite(FR_PWM,0);
  digitalWrite(RL_IN1,0); digitalWrite(RL_IN2,0); analogWrite(RL_PWM,0);
  digitalWrite(RR_IN1,0); digitalWrite(RR_IN2,0); analogWrite(RR_PWM,0);
}

static void driveOne(uint8_t pwm, uint8_t in1, uint8_t in2) {
  allOff();
  digitalWrite(in1, HIGH); digitalWrite(in2, LOW); analogWrite(pwm, 220);
}

static void clearFlips() {
  for (int i = 0; i < 8; i++) {
    prev[i] = digitalRead(EPINS[i]);
    flips[i] = 0;
  }
}

static void countFor(unsigned ms) {
  unsigned long t0 = millis();
  while (millis() - t0 < ms) {
    for (int i = 0; i < 8; i++) {
      uint8_t v = digitalRead(EPINS[i]);
      if (v != prev[i]) { flips[i]++; prev[i] = v; }
    }
  }
}

static void report(const char *name) {
  Serial.print(name);
  Serial.print(F(":"));
  for (int i = 0; i < 8; i++) {
    if (flips[i] < 20) continue;
    Serial.print(' ');
    Serial.print(EPINS[i]);
    Serial.print('=');
    Serial.print(flips[i]);
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  pinMode(FL_IN1, OUTPUT); pinMode(FL_IN2, OUTPUT); pinMode(FL_PWM, OUTPUT);
  pinMode(FR_IN1, OUTPUT); pinMode(FR_IN2, OUTPUT); pinMode(FR_PWM, OUTPUT);
  pinMode(RL_IN1, OUTPUT); pinMode(RL_IN2, OUTPUT); pinMode(RL_PWM, OUTPUT);
  pinMode(RR_IN1, OUTPUT); pinMode(RR_IN2, OUTPUT); pinMode(RR_PWM, OUTPUT);
  for (int i = 0; i < 8; i++) pinMode(EPINS[i], INPUT_PULLUP);
  allOff();
  delay(500);
  Serial.println(F("MAP start"));

  driveOne(FL_PWM, FL_IN1, FL_IN2); clearFlips(); countFor(1800); allOff(); report("FL");
  delay(400);
  driveOne(FR_PWM, FR_IN1, FR_IN2); clearFlips(); countFor(1800); allOff(); report("FR");
  delay(400);
  driveOne(RL_PWM, RL_IN1, RL_IN2); clearFlips(); countFor(1800); allOff(); report("RL");
  delay(400);
  driveOne(RR_PWM, RR_IN1, RR_IN2); clearFlips(); countFor(1800); allOff(); report("RR");
  Serial.println(F("DONE"));
}

void loop() { delay(1000); }
