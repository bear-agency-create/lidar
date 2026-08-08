/*
  WheelSweep MAX — по одному колесу на PWM 255, потом все вперёд.
  Если колесо молчит — нет силового питания драйверов / E-stop / провод.
*/
static const uint8_t FL_PWM = 8,  FL_IN1 = 9,  FL_IN2 = 10;
static const uint8_t FR_PWM = 7,  FR_IN1 = 5,  FR_IN2 = 6;
static const uint8_t RL_PWM = 13, RL_IN1 = 12, RL_IN2 = 11;
static const uint8_t RR_PWM = 2,  RR_IN1 = 3,  RR_IN2 = 4;
static const int PWM = 255;

static void coast(uint8_t pwm, uint8_t in1, uint8_t in2) {
  digitalWrite(in1, LOW); digitalWrite(in2, LOW); analogWrite(pwm, 0);
}
static void stopAll() {
  coast(FL_PWM, FL_IN1, FL_IN2);
  coast(FR_PWM, FR_IN1, FR_IN2);
  coast(RL_PWM, RL_IN1, RL_IN2);
  coast(RR_PWM, RR_IN1, RR_IN2);
}
static void spin(uint8_t pwm, uint8_t in1, uint8_t in2, bool fwd) {
  digitalWrite(in1, fwd ? LOW : HIGH);
  digitalWrite(in2, fwd ? HIGH : LOW);
  analogWrite(pwm, PWM);
}

void setup() {
  Serial.begin(115200);
  pinMode(FL_IN1, OUTPUT); pinMode(FL_IN2, OUTPUT); pinMode(FL_PWM, OUTPUT);
  pinMode(FR_IN1, OUTPUT); pinMode(FR_IN2, OUTPUT); pinMode(FR_PWM, OUTPUT);
  pinMode(RL_IN1, OUTPUT); pinMode(RL_IN2, OUTPUT); pinMode(RL_PWM, OUTPUT);
  pinMode(RR_IN1, OUTPUT); pinMode(RR_IN2, OUTPUT); pinMode(RR_PWM, OUTPUT);
  stopAll();
  Serial.println(F("READY WheelSweepMAX"));
  delay(1500);

  Serial.println(F("FL"));
  spin(FL_PWM, FL_IN1, FL_IN2, true); delay(1200); stopAll(); delay(400);
  Serial.println(F("FR"));
  spin(FR_PWM, FR_IN1, FR_IN2, true); delay(1200); stopAll(); delay(400);
  Serial.println(F("RL"));
  spin(RL_PWM, RL_IN1, RL_IN2, true); delay(1200); stopAll(); delay(400);
  Serial.println(F("RR"));
  spin(RR_PWM, RR_IN1, RR_IN2, true); delay(1200); stopAll(); delay(400);

  Serial.println(F("ALL_FWD"));
  spin(FL_PWM, FL_IN1, FL_IN2, true);
  spin(FR_PWM, FR_IN1, FR_IN2, true);
  spin(RL_PWM, RL_IN1, RL_IN2, true);
  spin(RR_PWM, RR_IN1, RR_IN2, true);
  delay(2000);
  stopAll();
  Serial.println(F("DONE"));
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'x' || c == 'X') stopAll();
  }
}
