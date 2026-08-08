/*
  EmergencyStop — coasts all motor pins, never drives.
*/
static const uint8_t PINS[][3] = {
  {8, 9, 10}, {7, 5, 6}, {13, 12, 11}, {2, 3, 4},
};

static void coast() {
  for (unsigned i = 0; i < 4; i++) {
    digitalWrite(PINS[i][1], LOW);
    digitalWrite(PINS[i][2], LOW);
    analogWrite(PINS[i][0], 0);
  }
}

void setup() {
  Serial.begin(115200);
  for (unsigned i = 0; i < 4; i++) {
    pinMode(PINS[i][0], OUTPUT);
    pinMode(PINS[i][1], OUTPUT);
    pinMode(PINS[i][2], OUTPUT);
  }
  coast();
  Serial.println(F("STOPPED"));
}

void loop() {
  coast();
  delay(50);
}
