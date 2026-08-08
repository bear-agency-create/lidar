/*
  InfiniteFwd MAX — едет вперёд на PWM 255 без остановки,
  пока не придёт x / STOP по Serial.
*/
static const uint8_t FL_PWM = 8,  FL_IN1 = 9,  FL_IN2 = 10;
static const uint8_t FR_PWM = 7,  FR_IN1 = 5,  FR_IN2 = 6;
static const uint8_t RL_PWM = 13, RL_IN1 = 12, RL_IN2 = 11;
static const uint8_t RR_PWM = 2,  RR_IN1 = 3,  RR_IN2 = 4;
static const int PWM = 255;

static void coastAll() {
  digitalWrite(FL_IN1, LOW); digitalWrite(FL_IN2, LOW); analogWrite(FL_PWM, 0);
  digitalWrite(FR_IN1, LOW); digitalWrite(FR_IN2, LOW); analogWrite(FR_PWM, 0);
  digitalWrite(RL_IN1, LOW); digitalWrite(RL_IN2, LOW); analogWrite(RL_PWM, 0);
  digitalWrite(RR_IN1, LOW); digitalWrite(RR_IN2, LOW); analogWrite(RR_PWM, 0);
}

static void driveFwd() {
  digitalWrite(FL_IN1, LOW);  digitalWrite(FL_IN2, HIGH); analogWrite(FL_PWM, PWM);
  digitalWrite(FR_IN1, LOW);  digitalWrite(FR_IN2, HIGH); analogWrite(FR_PWM, PWM);
  digitalWrite(RL_IN1, HIGH); digitalWrite(RL_IN2, LOW);  analogWrite(RL_PWM, PWM);
  digitalWrite(RR_IN1, HIGH); digitalWrite(RR_IN2, LOW);  analogWrite(RR_PWM, PWM);
}

void setup() {
  Serial.begin(115200);
  pinMode(FL_IN1, OUTPUT); pinMode(FL_IN2, OUTPUT); pinMode(FL_PWM, OUTPUT);
  pinMode(FR_IN1, OUTPUT); pinMode(FR_IN2, OUTPUT); pinMode(FR_PWM, OUTPUT);
  pinMode(RL_IN1, OUTPUT); pinMode(RL_IN2, OUTPUT); pinMode(RL_PWM, OUTPUT);
  pinMode(RR_IN1, OUTPUT); pinMode(RR_IN2, OUTPUT); pinMode(RR_PWM, OUTPUT);
  coastAll();
  delay(500);
  driveFwd();
  Serial.println(F("RUNNING FWD FOREVER — send x to stop"));
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == 'x' || c == 'X' || c == ' ') {
      coastAll();
      Serial.println(F("STOP_OK"));
    }
    if (c == 'w' || c == 'W' || c == 'f' || c == 'F') {
      driveFwd();
      Serial.println(F("FWD_OK"));
    }
  }
  // keep driving (re-assert in case of glitch)
  static unsigned long last = 0;
  unsigned long now = millis();
  if (now - last > 200) {
    last = now;
    driveFwd();
  }
}
