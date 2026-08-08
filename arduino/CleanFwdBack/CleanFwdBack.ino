/*
  CleanFwdBack MAX — самый мощный холостой проезд вперёд/назад.
  Пины как на роботе (Mega + L298), без PID / yaw / teleop / карты.
  PWM = 255 на все колёса.

  Serial 115200:
    f / FWD / w  — вперёд
    b / BACK / s — назад
    x / STOP     — стоп
    PING         — PONG
    AUTO         — вперёд → пауза → назад (один цикл)
*/

static const uint8_t FL_PWM = 8,  FL_IN1 = 9,  FL_IN2 = 10;
static const uint8_t FR_PWM = 7,  FR_IN1 = 5,  FR_IN2 = 6;
// RL IN swapped vs silk (same as GitHub MecanumTeleopBridge)
static const uint8_t RL_PWM = 13, RL_IN1 = 12, RL_IN2 = 11;
static const uint8_t RR_PWM = 2,  RR_IN1 = 3,  RR_IN2 = 4;

static const int PWM_RUN = 255;              // full H-bridge duty
static const unsigned long MOVE_MS = 2500;   // 2.5 s each way
static const unsigned long GAP_MS = 700;

static char lineBuf[40];
static uint8_t lineLen = 0;

static void coast(uint8_t pwm, uint8_t in1, uint8_t in2) {
  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
  analogWrite(pwm, 0);
}

static void stopAll() {
  coast(FL_PWM, FL_IN1, FL_IN2);
  coast(FR_PWM, FR_IN1, FR_IN2);
  coast(RL_PWM, RL_IN1, RL_IN2);
  coast(RR_PWM, RR_IN1, RR_IN2);
}

// Body-forward pin map (matches GitHub driveFL/FR/RL/RR for +v).
static void driveFwd() {
  // FL +
  digitalWrite(FL_IN1, LOW);  digitalWrite(FL_IN2, HIGH); analogWrite(FL_PWM, PWM_RUN);
  // FR + (SIGN_FR=-1 → same electrical as FL for +v)
  digitalWrite(FR_IN1, LOW);  digitalWrite(FR_IN2, HIGH); analogWrite(FR_PWM, PWM_RUN);
  // RL +
  digitalWrite(RL_IN1, HIGH); digitalWrite(RL_IN2, LOW);  analogWrite(RL_PWM, PWM_RUN);
  // RR +
  digitalWrite(RR_IN1, HIGH); digitalWrite(RR_IN2, LOW);  analogWrite(RR_PWM, PWM_RUN);
}

// Body-back = invert all IN
static void driveBack() {
  digitalWrite(FL_IN1, HIGH); digitalWrite(FL_IN2, LOW);  analogWrite(FL_PWM, PWM_RUN);
  digitalWrite(FR_IN1, HIGH); digitalWrite(FR_IN2, LOW);  analogWrite(FR_PWM, PWM_RUN);
  digitalWrite(RL_IN1, LOW);  digitalWrite(RL_IN2, HIGH); analogWrite(RL_PWM, PWM_RUN);
  digitalWrite(RR_IN1, LOW);  digitalWrite(RR_IN2, HIGH); analogWrite(RR_PWM, PWM_RUN);
}

static void runFor(void (*fn)(), unsigned long ms, const char *tag) {
  Serial.print(F("RUN "));
  Serial.println(tag);
  fn();
  delay(ms);
  stopAll();
  Serial.println(F("STOP"));
}

static void autoTrip() {
  Serial.println(F("AUTO_START"));
  delay(500);
  runFor(driveFwd, MOVE_MS, "FWD");
  delay(GAP_MS);
  runFor(driveBack, MOVE_MS, "BACK");
  delay(GAP_MS);
  Serial.println(F("AUTO_DONE"));
}

static void handleLine(char *line) {
  if (!line[0]) return;
  if (!strcmp(line, "PING")) { Serial.println(F("PONG")); return; }
  if (!strcmp(line, "STOP") || !strcmp(line, "x") || !strcmp(line, "X")) {
    stopAll(); Serial.println(F("STOP_OK")); return;
  }
  if (!strcmp(line, "FWD") || !strcmp(line, "f") || !strcmp(line, "F") || !strcmp(line, "w")) {
    runFor(driveFwd, MOVE_MS, "FWD"); return;
  }
  if (!strcmp(line, "BACK") || !strcmp(line, "b") || !strcmp(line, "B") || !strcmp(line, "s")) {
    runFor(driveBack, MOVE_MS, "BACK"); return;
  }
  if (!strcmp(line, "AUTO")) { autoTrip(); return; }
}

void setup() {
  Serial.begin(115200);
  pinMode(FL_IN1, OUTPUT); pinMode(FL_IN2, OUTPUT); pinMode(FL_PWM, OUTPUT);
  pinMode(FR_IN1, OUTPUT); pinMode(FR_IN2, OUTPUT); pinMode(FR_PWM, OUTPUT);
  pinMode(RL_IN1, OUTPUT); pinMode(RL_IN2, OUTPUT); pinMode(RL_PWM, OUTPUT);
  pinMode(RR_IN1, OUTPUT); pinMode(RR_IN2, OUTPUT); pinMode(RR_PWM, OUTPUT);
  stopAll();
  Serial.println(F("READY CleanFwdBack"));
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen) {
        lineBuf[lineLen] = 0;
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
