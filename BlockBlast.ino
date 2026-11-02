
#define PIN_JOY_X   39   // joystick VRx  (grey wire)
#define PIN_JOY_Y   32   // joystick VRy  (purple wire)
#define PIN_JOY_SW  33   // joystick SW   (blue wire)
#define PIN_POT     15   // potentiometer wiper (green wire)
#define PIN_BTN      2   // breadboard push button (blue wire, other leg to GND)
#define PIN_LED     25   // LED (not fitted - harmless)
// ---------------------------------------------------------------------

#define BAUD        115200
#define GRID_W      8
#define GRID_H      8
#define JOY_DEADZONE 650
#define MOVE_REPEAT_MS 150
#define DEBOUNCE_MS  30

// ---------- Shapes ---------------------------------------------------
struct Shape { uint8_t w, h; const char* cells; };   // row-major, '#' = filled

const Shape SHAPES[] = {
  {1,1,"#"},
  {2,1,"##"},            {1,2,"##"},
  {3,1,"###"},           {1,3,"###"},
  {4,1,"####"},          {1,4,"####"},
  {5,1,"#####"},         {1,5,"#####"},
  {2,2,"####"},
  {3,3,"#########"},
  {3,2,"######"},        {2,3,"######"},
  {2,2,"#.##"}, {2,2,".###"}, {2,2,"###."}, {2,2,"##.#"},                 // small L
  {3,3,"#..#..###"}, {3,3,"..#..####"}, {3,3,"###..#..#"}, {3,3,"####..#.."}, // big L
  {3,2,"###.#."}, {3,2,".#.###"}, {2,3,"#.###."}, {2,3,".###.#"},        // T
  {3,2,".####."}, {3,2,"##..##"}, {2,3,"#.##.#"}, {2,3,".####."},        // S / Z
};
const int NUM_SHAPES = sizeof(SHAPES) / sizeof(SHAPES[0]);

// ---------- Game state ----------------------------------------------
uint8_t grid[GRID_H][GRID_W];     // 0 empty, 1..7 colour id
int8_t  pieces[3];                // shape index, or -1 if already used
int     sel = 0;                  // highlighted piece (from pot)
int     cx = 0, cy = 0;           // cursor (top-left of piece)
long    score = 0;
int     combo = 0;
bool    gameOver = false;
enum Mode { SELECT, PLACE };
Mode    mode = SELECT;
bool    dirty = true;

// ---------- Input state ---------------------------------------------
int  joyCenterX = 2048, joyCenterY = 2048;
unsigned long lastMove = 0;
bool joyHeld = false;

struct Button {
  uint8_t pin; bool stable, last; unsigned long t;
  Button(uint8_t p) : pin(p), stable(true), last(true), t(0) {}
  bool pressed() {               // true once on falling edge
    bool r = digitalRead(pin);
    if (r != last) { t = millis(); last = r; }
    if (millis() - t > DEBOUNCE_MS && r != stable) {
      stable = r;
      if (!stable) return true;
    }
    return false;
  }
};
Button btnPick(PIN_BTN), btnDrop(PIN_JOY_SW);

// ---------- LED helpers ---------------------------------------------
void blink(int times, int ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(PIN_LED, HIGH); delay(ms);
    digitalWrite(PIN_LED, LOW);  delay(ms);
  }
}

// ---------- Game helpers --------------------------------------------
bool cellFilled(const Shape& s, int r, int c) { return s.cells[r * s.w + c] == '#'; }

bool fits(int shapeIdx, int x, int y) {
  const Shape& s = SHAPES[shapeIdx];
  if (x < 0 || y < 0 || x + s.w > GRID_W || y + s.h > GRID_H) return false;
  for (int r = 0; r < s.h; r++)
    for (int c = 0; c < s.w; c++)
      if (cellFilled(s, r, c) && grid[y + r][x + c]) return false;
  return true;
}

bool fitsAnywhere(int shapeIdx) {
  for (int y = 0; y < GRID_H; y++)
    for (int x = 0; x < GRID_W; x++)
      if (fits(shapeIdx, x, y)) return true;
  return false;
}

void refillPieces() {
  for (int i = 0; i < 3; i++) pieces[i] = random(NUM_SHAPES);
}

void clampCursor() {
  const Shape& s = SHAPES[pieces[sel]];
  cx = constrain(cx, 0, GRID_W - s.w);
  cy = constrain(cy, 0, GRID_H - s.h);
}

int clearLines() {
  bool rowFull[GRID_H], colFull[GRID_W];
  int lines = 0;
  for (int y = 0; y < GRID_H; y++) {
    rowFull[y] = true;
    for (int x = 0; x < GRID_W; x++) if (!grid[y][x]) { rowFull[y] = false; break; }
    if (rowFull[y]) lines++;
  }
  for (int x = 0; x < GRID_W; x++) {
    colFull[x] = true;
    for (int y = 0; y < GRID_H; y++) if (!grid[y][x]) { colFull[x] = false; break; }
    if (colFull[x]) lines++;
  }
  for (int y = 0; y < GRID_H; y++)
    for (int x = 0; x < GRID_W; x++)
      if (rowFull[y] || colFull[x]) grid[y][x] = 0;
  return lines;
}

void placePiece() {
  int idx = pieces[sel];
  if (idx < 0 || !fits(idx, cx, cy)) { blink(2, 40); return; }
  const Shape& s = SHAPES[idx];
  int cells = 0;
  uint8_t colour = (idx % 7) + 1;
  for (int r = 0; r < s.h; r++)
    for (int c = 0; c < s.w; c++)
      if (cellFilled(s, r, c)) { grid[cy + r][cx + c] = colour; cells++; }
  score += cells;

  int lines = clearLines();
  if (lines > 0) {
    combo++;
    score += lines * 10 * lines + combo * 10;   // bonus for multi-line & combos
    blink(lines, 80);
  } else combo = 0;

  pieces[sel] = -1;
  bool anyLeft = false;
  for (int i = 0; i < 3; i++) if (pieces[i] >= 0) anyLeft = true;
  if (!anyLeft) refillPieces();

  // game over check
  bool canMove = false;
  for (int i = 0; i < 3; i++) if (pieces[i] >= 0 && fitsAnywhere(pieces[i])) canMove = true;
  if (!canMove) gameOver = true;

  mode = SELECT;
  dirty = true;
}

void newGame() {
  memset(grid, 0, sizeof(grid));
  refillPieces();
  score = 0; combo = 0; gameOver = false; mode = SELECT; cx = cy = 0;
  dirty = true;
}

// ---------- Serial frame --------------------------------------------
// F;score;mode;sel;cx;cy;over;grid(64 digits);p0;p1;p2   piece = w,h,cells or -
void sendFrame() {
  Serial.print("F;"); Serial.print(score);
  Serial.print(';');  Serial.print(mode == PLACE ? 1 : 0);
  Serial.print(';');  Serial.print(sel);
  Serial.print(';');  Serial.print(cx);
  Serial.print(';');  Serial.print(cy);
  Serial.print(';');  Serial.print(gameOver ? 1 : 0);
  Serial.print(';');
  for (int y = 0; y < GRID_H; y++)
    for (int x = 0; x < GRID_W; x++) Serial.print(grid[y][x]);
  for (int i = 0; i < 3; i++) {
    Serial.print(';');
    if (pieces[i] < 0) Serial.print('-');
    else {
      const Shape& s = SHAPES[pieces[i]];
      Serial.print(s.w); Serial.print(','); Serial.print(s.h); Serial.print(',');
      Serial.print(s.cells); Serial.print(','); Serial.print((pieces[i] % 7) + 1);
    }
  }
  Serial.println();
}

// ---------- Input reading -------------------------------------------
void readPot() {
  int raw = analogRead(PIN_POT);
  int cand = raw < 1365 ? 0 : (raw < 2730 ? 1 : 2);
  // hysteresis: only switch if comfortably past the boundary
  int boundary = (cand == 0) ? 1365 : (cand == 2 ? 2730 : (sel == 0 ? 1365 : 2730));
  if (cand != sel && abs(raw - boundary) > 120) { sel = cand; dirty = true; }
}

void readJoystick() {
  int dx = analogRead(PIN_JOY_X) - joyCenterX;
  int dy = analogRead(PIN_JOY_Y) - joyCenterY;
  int mx = 0, my = 0;
  if (abs(dx) > JOY_DEADZONE) mx = dx > 0 ? 1 : -1;
  if (abs(dy) > JOY_DEADZONE) my = dy > 0 ? 1 : -1;

  if (mx == 0 && my == 0) { joyHeld = false; return; }
  unsigned long now = millis();
  if (!joyHeld || now - lastMove > MOVE_REPEAT_MS) {
    cx += mx; cy += my;
    clampCursor();
    lastMove = now; joyHeld = true; dirty = true;
  }
}

// ---------- Arduino --------------------------------------------------
void setup() {
  Serial.begin(BAUD);
  pinMode(PIN_JOY_SW, INPUT_PULLUP);
  pinMode(PIN_BTN,    INPUT_PULLUP);
  pinMode(PIN_LED,    OUTPUT);
  analogReadResolution(12);
  randomSeed(analogRead(PIN_POT) ^ (analogRead(PIN_JOY_X) << 4) ^ micros());

  // calibrate joystick centre (leave it alone at boot)
  long sx = 0, sy = 0;
  for (int i = 0; i < 32; i++) { sx += analogRead(PIN_JOY_X); sy += analogRead(PIN_JOY_Y); delay(2); }
  joyCenterX = sx / 32; joyCenterY = sy / 32;

  newGame();
  blink(3, 60);
}

void loop() {
  static unsigned long lastHeartbeat = 0;

  // commands from the viewer: 'N' = new game
  while (Serial.available()) {
    if (Serial.read() == 'N') newGame();
  }

  if (gameOver) {
    digitalWrite(PIN_LED, (millis() / 120) % 2);
    if (btnPick.pressed()) newGame();
    btnDrop.pressed();
  } else {
    readPot();

    if (mode == SELECT) {
      digitalWrite(PIN_LED, LOW);
      if (btnPick.pressed() && pieces[sel] >= 0) {
        mode = PLACE; clampCursor(); dirty = true;
      }
      btnDrop.pressed();                       // keep debouncer fresh
    } else {                                    // PLACE
      digitalWrite(PIN_LED, HIGH);
      readJoystick();
      if (btnDrop.pressed()) placePiece();
      if (btnPick.pressed()) { mode = SELECT; dirty = true; }   // cancel
      if (pieces[sel] < 0) { mode = SELECT; dirty = true; }     // pot moved to empty slot
    }
  }

  if (dirty || millis() - lastHeartbeat > 500) {
    sendFrame();
    dirty = false;
    lastHeartbeat = millis();
  }
  delay(10);
}
