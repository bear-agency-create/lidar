/*
  BruteFwd — infinite forward, pin map A (code) then if you reflash map B (README RL swap).
  Also forces pins 2-13 as outputs briefly so ENA jumpers aren't the only path.
  MAP=0: FL 8/9/10, FR 7/5/6, RL 13/12/11, RR 2/3/4  (current .ino)
  MAP=1: FL 8/9/10, FR 7/5/6, RL 13/11/12, RR 2/3/4  (README)
*/
#ifndef PIN_MAP
#define PIN_MAP 0
#endif

#if PIN_MAP == 0
static const uint8_t W[4][3] = {
  {8, 9, 10},   // FL pwm in1 in2
  {7, 5, 6},    // FR
  {13, 12, 11}, // RL
  {2, 3, 4},    // RR
};
#else
static const uint8_t W[4][3] = {
  {8, 9, 10},
  {7, 5, 6},
  {13, 11, 12}, // RL README swap
  {2, 3, 4},
};
#endif

static const int PWM = 255;

static void coast() {
  for (int i = 0; i < 4; i++) {
    digitalWrite(W[i][1], LOW);
    digitalWrite(W[i][2], LOW);
    analogWrite(W[i][0], 0);
  }
}

static void fwd() {
  // Same electrical forward as CleanFwdBack / InfiniteFwd
  // FL/FR: IN1 LOW IN2 HIGH; RL/RR: IN1 HIGH IN2 LOW
  digitalWrite(W[0][1], LOW);  digitalWrite(W[0][2], HIGH); analogWrite(W[0][0], PWM);
  digitalWrite(W[1][1], LOW);  digitalWrite(W[1][2], HIGH); analogWrite(W[1][0], PWM);
  digitalWrite(W[2][1], HIGH); digitalWrite(W[2][2], LOW);  analogWrite(W[2][0], PWM);
  digitalWrite(W[3][1], HIGH); digitalWrite(W[3][2], LOW);  analogWrite(W[3][0], PWM);
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    pinMode(W[i][0], OUTPUT);
    pinMode(W[i][1], OUTPUT);
    pinMode(W[i][2], OUTPUT);
  }
  coast();
  delay(300);
  fwd();
  Serial.print(F("BRUTE_FWD map="));
  Serial.println(PIN_MAP);
  Serial.println(F("If silent: motor 12V / E-stop / L298 jumpers — NOT USB code"));
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'x' || c == 'X') { coast(); Serial.println(F("STOP_OK")); }
    if (c == 'w' || c == 'W') { fwd(); Serial.println(F("FWD_OK")); }
  }
  static unsigned long t;
  if (millis() - t > 150) { t = millis(); fwd(); }
}
