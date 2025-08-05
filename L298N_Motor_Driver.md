## 🔌 L298N Motor Driver with 4 Wheels

This chapter focuses on the **L298N motor driver**, which powers the four-wheel setup of your Raspberry Pi 5 car project. Here’s a look at the L298N motor driver component:

![L298N Motor Driver Component](images)

The L298N can be a bit tricky for beginners 😅, especially with its **H-bridge circuit**. But don’t worry—we’ll walk through it step by step 👣.

### 🧠 What’s an H-Bridge?
Imagine it like a road system with four switches: **S1, S2, S3, and S4** 🚦

- 🔁 For the wheel to spin **clockwise (forward)**:
  - Turn on S1 and S4 ✅
  - Turn off S2 and S3 ❌
  - This lets current flow in one direction 🟢

  ![Clockwise Circuit Picture](images)

- 🔁 For **anticlockwise (backward)**:
  - Turn on S2 and S3 ✅
  - Turn off S1 and S4 ❌
  - This reverses the current 🔄

  ![Anticlockwise Circuit Picture](images)

Let’s connect this idea to the **real L298N driver**.

Here’s a full diagram showing L298N connected to 4 wheels, a 12V battery, and your Pi 5:

![Full L298N Circuit with 4 Wheels](images/l298n_full_circuit.jpg)

---

### 🔌 Pin Connections

| Pin Name    | Connection            |
|-------------|------------------------|
| ENA_GPIO    | GPIO 24               |
| IN1_GPIO    | GPIO 17               |
| IN2_GPIO    | GPIO 18               |
| ENB_GPIO    | GPIO 25               |
| IN3_GPIO    | GPIO 22               |
| IN4_GPIO    | GPIO 23               |
| 12V         | 12V Battery Holder    |
| GND         | GND                   |
| 5V          | 5V Pin on Pi 5        |

The **IN1–IN4 pins** act like the switches above (S1–S4), turning on/off to control wheel direction.

---

### 🔄 Wheel Direction Control

#### ➡️ Forward
| Action      | IN1 | IN2 | IN3 | IN4 |
|-------------|-----|-----|-----|-----|
| Forward     | on  | off | off | on  |

#### ⬅️ Backward
| Action      | IN1 | IN2 | IN3 | IN4 |
|-------------|-----|-----|-----|-----|
| Backward    | off | on  | on  | off |

#### ↪️ Turn Left
| Action      | IN1 | IN2 | IN3 | IN4 |
|-------------|-----|-----|-----|-----|
| Left        | on  | off | off | off |

#### ↩️ Turn Right
| Action      | IN1 | IN2 | IN3 | IN4 |
|-------------|-----|-----|-----|-----|
| Right       | off | off | off | on  |

---

### 🧾 Code for Wheel Direction
This code defines how to control wheel directions by toggling the GPIO pins:

```python
# --- GPIO Pin Definitions ---
ENA_GPIO = 24
IN1_GPIO = 17
IN2_GPIO = 27
ENB_GPIO = 25
IN3_GPIO = 22
IN4_GPIO = 23

# --- Initialize GPIO Zero Devices ---
in1 = DigitalOutputDevice(IN1_GPIO)
in2 = DigitalOutputDevice(IN2_GPIO)
ena = PWMOutputDevice(ENA_GPIO)
in3 = DigitalOutputDevice(IN3_GPIO)
in4 = DigitalOutputDevice(IN4_GPIO)
enb = PWMOutputDevice(ENB_GPIO)

def move_forward(speed):
    in1.on(); in2.off()
    in3.off(); in4.on()
    ena.value = speed
    enb.value = speed
    print(f"Action: Forward at {speed:.2f}")

def move_backward(speed):
    in1.off(); in2.on()
    in3.on(); in4.off()
    ena.value = speed
    enb.value = speed
    print(f"Action: Backward at {speed:.2f}")

def turn_left(speed):
    in1.on(); in2.off()
    in3.off(); in4.off()
    ena.value = speed
    enb.value = 0.0
    print(f"Action: Left (L:{speed:.2f}, R:0.0)")

def turn_right(speed):
    in1.off(); in2.off()
    in3.off(); in4.on()
    ena.value = 0.0
    enb.value = speed
    print(f"Action: Right (L:0.0, R:{speed:.2f})")
```

---

### ⚙️ PWM for Speed Control

PWM = **Pulse Width Modulation** (fancy way to say "control motor speed")

Your car uses different speeds for different control modes:

- 💨 **Full Speed** (iPad, Switch Controller, Voice Control):
  ```python
  MAX_PWM_SPEED = 1.0
  ```
- 🐢 **Slower Speed** (Gesture Mode):
  ```python
  BASE_SPEED = 0.4
  ```

By adjusting `ena.value` and `enb.value`, you make the wheels spin faster or slower. 
