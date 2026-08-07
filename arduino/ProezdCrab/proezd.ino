/*
  Тележка, 4 мотора:
  ЛВ — левый верхний
  ЛН — левый нижний
  ПВ — правый верхний
  ПН — правый нижний

  Подключение через драйвер (L298N и т.п.):
  каждый мотор — 2 пина: IN1 и IN2
  вперед  = IN1 HIGH, IN2 LOW
  назад   = IN1 LOW,  IN2 HIGH
*/

// Левый верхний
#define LV_IN1 2
#define LV_IN2 3

// Левый нижний
#define LN_IN1 4
#define LN_IN2 5

// Правый верхний
#define PV_IN1 6
#define PV_IN2 7

// Правый нижний
#define PN_IN1 8
#define PN_IN2 9

void motor(int in1, int in2, bool vpered) {
  digitalWrite(in1, vpered ? HIGH : LOW);
  digitalWrite(in2, vpered ? LOW : HIGH);
}

void stopMotor(int in1, int in2) {
  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
}

void stopAll() {
  stopMotor(LV_IN1, LV_IN2);
  stopMotor(LN_IN1, LN_IN2);
  stopMotor(PV_IN1, PV_IN2);
  stopMotor(PN_IN1, PN_IN2);
}

// Проезд направо
void vpravo() {
  motor(PV_IN1, PV_IN2, false);  // правый верхний — назад
  motor(PN_IN1, PN_IN2, true);    // правый нижний — вперед
  motor(LV_IN1, LV_IN2, false);   // левый верхний — назад
  motor(LN_IN1, LN_IN2, true);    // левый нижний — вперед
}

// Проезд налево (наоборот)
void vlevo() {
  motor(PV_IN1, PV_IN2, true);    // правый верхний — вперед
  motor(PN_IN1, PN_IN2, false);   // правый нижний — назад
  motor(LV_IN1, LV_IN2, true);    // левый верхний — вперед
  motor(LN_IN1, LN_IN2, false);    // левый нижний — назад
}

void setup() {
  pinMode(LV_IN1, OUTPUT);
  pinMode(LV_IN2, OUTPUT);
  pinMode(LN_IN1, OUTPUT);
  pinMode(LN_IN2, OUTPUT);
  pinMode(PV_IN1, OUTPUT);
  pinMode(PV_IN2, OUTPUT);
  pinMode(PN_IN1, OUTPUT);
  pinMode(PN_IN2, OUTPUT);

  stopAll();
}

void loop() {
  vpravo();
  delay(2000);
  stopAll();
  delay(500);

  vlevo();
  delay(2000);
  stopAll();
  delay(500);
}
