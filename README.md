# Block Blast

Build a handheld Block Blast game, with an ESP32, joystick, potentiometer, push button and a breadboard, with game displayed over a Pygame viewer on a Macbook. 

**Blog post with the full write-up, design decisions, and videos:** https://ishanimitra-19.github.io/CES-ishanimitra.github.io/module2.html

![Block Blast gameplay](media/blockblast_demo.gif)

## What it is

Block Blast is like Tetris, except the blocks don't fall. Instead, you are given three pieces at a time, and must use deduction to fit them into the 8x8 grid. Once you fill a row or column, it is cleared and your score increases. You lose once you can't fit any more pieces, when you get "blocked out". 
Normally, this is played on a touch screen, but this version allows you to play with a physical controller. 

| Control | What it does |
| --- | --- |
| Potentiometer | Chooses which of the three pieces is selected |
| Push button (breadboard) | Selects the piece |
| Joystick | Moves around the 8x8 grid |
| Joystick button | Places the piece on the grid |

## Hardware

- ESP32
- Analog joystick 
- Potentiometer 
- Push button
- Breadboard
- Jumper wires
- USB-C cable

## Wiring

| Component pin | ESP32 GPIO |
| --- | --- |
| Potentiometer| Use small jumpers to connect to + and - charge, each jumper should be aligned next to the top and bottom legs of the pot. Use one long jumper aligned next to the middle leg of the pot, and plug the other end of the jumper into a pin that is beside the header of the ESP. |
| Push Button | Use a small jumper connected to the pin next to the leg of the button into the - charge, and use a long jumper to connect the other leg to a pin next to the ESP header|
| ESP 32 | Use two jumpers to connect from a pin next to the header, to a - and + pin |
| Joystick | Connect the blue, purple, and grey wires (in a row) into pins next to the headers. Connect the white joystick wire into the - charge, and the black joystick wire into the + charge. Use one small jumper to connect the bottom right header pin to the + charge next to the ESP |

# Optional 
Use extra long jumpers to secure the joystick to the right side of the breadboard, but do not wire anything into the + or - pins. This is simply to keep the joystick on the breadboard to make game play more practical. 

### Fritzing diagram

![Breadboard diagram](fritzing/blockblast_breadboard.png)

The editable sketch is in [`fritzing/blockblast.fzz`](fritzing/blockblast.fzz) (the TTGO and joystick parts are bundled inside it).


## How to run

### 1. Flash the ESP32
1. Open BlockBlast.ino in Arduino IDE
2. Select the board ESP 32 Dev Module and your USB port.
3. Upload sketch. 

### 2. Run in terminal

```
pip3 install pygame pyserial numpy
python3 viewer.py
```

### 3. Play

1. Turn the potentiometer to highlight one of the three pieces.
2. Press the breadboard button to pick it up.
3. Move it with the joystick.
4. Press the joystick down to drop it (or press the breadboard button again to cancel and pick a different piece).
5. After a game over, press the breadboard button to start a new game.

## Files

```
BlockBlast.ino                   ESP32 game logic and serial output
viewer.py                        Pygame viewer (reads serial, draws the board, plays music)
fritzing/blockblast.fzz          Fritzing sketch
fritzing/blockblast_breadboard.png  Breadboard diagram exported from Fritzing
media/blockblast_demo.gif        Gameplay demo
```

## AI use

The game code was generated with Claude (Fable 5.1) from a prompt describing the hardware and the desired controls, then iterated on to fix bugs and change the music. See the [blog post](https://ishanimitra-19.github.io/CES-ishanimitra.github.io/module2.html) for the exact prompt.
