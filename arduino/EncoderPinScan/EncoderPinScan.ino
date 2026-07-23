/*
  EncoderPinScan — find which Mega pins toggle while wheels spin.
  Motors use 2..13 (skipped). Polls 14..53 and A0..A15.
*/
#include <string.h>

static const uint8_t FL_PWM = 8,  FL_IN1 = 9,  FL_IN2 = 10;
static const uint8_t FR_PWM = 7,  FR_IN1 = 5,  FR_IN2 = 6;
static const uint8_t RL_PWM = 13, RL_IN1 = 11, RL_IN2 = 12;
static const uint8_t RR_PWM = 2,  RR_IN1 = 3,  RR_IN2 = 4;

static const int NMAX = 80;
static uint8_t pins[NMAX];
static uint8_t prev[NMAX];
static uint16_t flips[NMAX];
static int npins = 0;

static void motorOn(uint8_t pwm, uint8_t in1, uint8_t in2) {
  digitalWrite(in1, HIGH); digitalWrite(in2, LOW); analogWrite(pwm, 220);
}
static void motorOff(uint8_t pwm, uint8_t in1, uint8_t in2) {
  digitalWrite(in1, LOW); digitalWrite(in2, LOW); analogWrite(pwm, 0);
}

static bool isMotorPin(uint8_t p) {
  return p >= 2 && p <= 13;
}

void setup() {
  Serial.begin(115200);
  pinMode(FL_IN1, OUTPUT); pinMode(FL_IN2, OUTPUT); pinMode(FL_PWM, OUTPUT);
  pinMode(FR_IN1, OUTPUT); pinMode(FR_IN2, OUTPUT); pinMode(FR_PWM, OUTPUT);
  pinMode(RL_IN1, OUTPUT); pinMode(RL_IN2, OUTPUT); pinMode(RL_PWM, OUTPUT);
  pinMode(RR_IN1, OUTPUT); pinMode(RR_IN2, OUTPUT); pinMode(RR_PWM, OUTPUT);
  motorOff(FL_PWM, FL_IN1, FL_IN2);
  motorOff(FR_PWM, FR_IN1, FR_IN2);
  motorOff(RL_PWM, RL_IN1, RL_IN2);
  motorOff(RR_PWM, RR_IN1, RR_IN2);

  for (uint8_t p = 14; p <= 53; p++) {
    if (isMotorPin(p)) continue;
    if (npins >= NMAX) break;
    pinMode(p, INPUT_PULLUP);
    pins[npins] = p;
    prev[npins] = digitalRead(p);
    flips[npins] = 0;
    npins++;
  }
  for (uint8_t i = 0; i < 16; i++) {
    uint8_t p = A0 + i;
    if (npins >= NMAX) break;
    pinMode(p, INPUT_PULLUP);
    pins[npins] = p;
    prev[npins] = digitalRead(p);
    flips[npins] = 0;
    npins++;
  }

  Serial.print(F("SCAN pins=")); Serial.println(npins);
  Serial.println(F("Spinning motors 4s — watch flips"));
  motorOn(FL_PWM, FL_IN1, FL_IN2);
  motorOn(FR_PWM, FR_IN1, FR_IN2);
  motorOn(RL_PWM, RL_IN1, RL_IN2);
  motorOn(RR_PWM, RR_IN1, RR_IN2);

  unsigned long t0 = millis();
  while (millis() - t0 < 4000) {
    for (int i = 0; i < npins; i++) {
      uint8_t v = digitalRead(pins[i]);
      if (v != prev[i]) {
        flips[i]++;
        prev[i] = v;
      }
    }
  }

  motorOff(FL_PWM, FL_IN1, FL_IN2);
  motorOff(FR_PWM, FR_IN1, FR_IN2);
  motorOff(RL_PWM, RL_IN1, RL_IN2);
  motorOff(RR_PWM, RR_IN1, RR_IN2);

  Serial.println(F("RESULTS flips>0:"));
  int hits = 0;
  for (int i = 0; i < npins; i++) {
    if (flips[i] == 0) continue;
    hits++;
    Serial.print(F("  pin "));
    Serial.print(pins[i]);
    Serial.print(F(" flips="));
    Serial.println(flips[i]);
  }
  if (!hits) Serial.println(F("  NONE — encoders not on free pins or not connected"));
  Serial.println(F("DONE"));
}

void loop() {
  delay(1000);
}
