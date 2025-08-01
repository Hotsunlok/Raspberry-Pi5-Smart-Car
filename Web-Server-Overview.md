# 🌐 Web Server Overview

![Web Server on iPad](assets/webserver_ipad.jpg) <!-- Replace with actual filename -->

This is the **web interface** you'll see on your iPad after connecting to the Raspberry Pi 5 network.

---

### 🖼️ Title Area

One of the first things you’ll notice is the floating animated title at the top of the page:

![Web Server Title](assets/title_screenshot.jpg)

---
## 🧩 Features

### 🔽 1. Dropdown Mode Menu

The first feature is a **dropdown menu** that lets you choose from 4 different control modes:

1. 📱 iPad Buttons  
2. 🎮 Switch Controller  
3. 🗣️ Speech Recognition  
4. ✋ Gesture Recognition  

When you tap the menu on your iPad, it will look like this:

![Dropdown Menu Screenshot](assets/dropdown_menu.jpg) <!-- replace with your image later -->

Here’s the code used to create the dropdown:

```html
<select id="controlMode" onchange="changeControlMode()">
  <option value="ipad_buttons">iPad Buttons</option>
  <option value="switch_controller">Switch Controller</option>
  <option value="speech_recognition">Voice Control</option>
  <option value="gesture_recognition">Gesture Recognition</option>
</select>
```
---
### 📷 2. Webcam Streaming to the Web

This feature streams **live video** from the Logitech webcam directly to the center of the web server UI — right on your iPad screen!

📺 It’s super helpful for:
- Seeing the car’s surroundings in real time  
- Monitoring movement while using iPad Buttons, Switch Controller, Voice, or Gesture  
- Keeping full control without physically chasing the car around 😊

![Screenshot of Live Streaming](assets/live_stream.jpg) <!-- Replace with your actual screenshot -->

The video stream stays fixed at the center of the page and doesn’t disappear when you switch between control modes.


#### 💻 Code Behind the Stream Layout:

```html
<div class="video-container">
  <img id="camera" src="/video_feed" style="width: auto; max-width: 90%; height: 360px; aspect-ratio: 4 / 3; object-fit: contain; border-radius: 8px;" />
</div>
```
- The video-container class centers the webcam nicely.
- The camera element makes sure the stream stays at 360px height and adapts to screen size without distortion.
---
📎 If you're interested in **how the Logitech webcam was configured**,  
**how the MJPEG stream is sent to the web**,  
and **how it also detects hand gestures**...

👉 check out this chapter:  
🔗 [Logitech Webcam (used for video + hand gesture detection)](Logitech-Webcam.md)

---
### 🖱️ 3. iPad Web Control Buttons

This feature gives you a **touch-based controller** right on your iPad!  
When you choose **"iPad Buttons"** from the dropdown menu, you’ll see four buttons appear:

- ▲ Move Forward (top-left)
- ▼ Move Backward (bottom-left)
- ◀ Turn Left (bottom-right)
- ▶ Turn Right (top-right)

![iPad Button Layout Screenshot](assets/ipad_buttons.jpg)

Switch to any other mode (like 🎮 Controller, 🗣️ Voice, or ✋ Gesture), and these buttons will disappear automatically — super clean!


---

### 🎨 Button Style & Layout (HTML + CSS)

The design includes size, shape, color, and placement:

```html
<style>
  button {
    width: 90px;
    height: 90px;
    font-size: 36px;
    border-radius: 50%;
    border: none;
    color: white;
    background-color: #04AA6D; /* Green */
    box-shadow: 0 6px #666;
    cursor: pointer;
  }
  button:active {
    background-color: #3e8e41;
    box-shadow: 0 3px #444;
    transform: translateY(4px);
  }
</style>

<div id="ipadButtons">
  <div class="left-controls">
    <button ontouchstart="send('forward')" ontouchend="send('stop')">▲</button>
    <button ontouchstart="send('backward')" ontouchend="send('stop')">▼</button>
  </div>
  <div class="right-controls">
    <button ontouchstart="send('left')" ontouchend="send('stop')">◀</button>
    <button ontouchstart="send('right')" ontouchend="send('stop')">▶</button>
  </div>
</div>
```
### 🔁 Button Function Logic (Frontend → Backend)

When you tap a button, it sends a wireless command to the Raspberry Pi 5 to control the car using PWM (Pulse Width Modulation) for smooth motor control. Each button triggers this JavaScript function:

```html
<script>
  function send(cmd) {
    fetch('/' + cmd);
  }
</script>
```
Then it calls Flask routes like this on the Raspberry Pi:
```python
@app.route('/forward')
def forward_route():
    if current_control_mode == 'ipad_buttons':
        move_forward(MAX_PWM_SPEED)  # Uses PWM to set motor speed
    return '', 200

@app.route('/backward')
def backward_route():
    if current_control_mode == 'ipad_buttons':
        move_backward(MAX_PWM_SPEED)
    return '', 200

@app.route('/left')
def left_route():
    if current_control_mode == 'ipad_buttons':
        turn_left(MAX_PWM_SPEED)
    return '', 200

@app.route('/right')
def right_route():
    if current_control_mode == 'ipad_buttons':
        turn_right(MAX_PWM_SPEED)
    return '', 200

@app.route('/stop')
def stop_route():
    if current_control_mode == 'ipad_buttons':
        stop_motors()
    return '', 200
```
### ⚙️ What Happens Internally?
Example motor function:
```python
def move_forward(speed):
    in1.on(); in2.off()
    in3.off(); in4.on()
    ena.value = speed  # PWM speed control
    enb.value = speed
    green_led1.on()
    green_led2.on()
    print(f"Action: Forward at {speed:.2f}")
```
- The buttons send fetch commands like `/forward`
- Flask receives it and checks the current mode
- Then it uses **PWM signals** to spin the wheels
- When you lift your finger → `/stop` is sent → motors stop smoothly
---
📎 If you're curious about how **PWM signals** control the motors  
and how the **L298N driver moves 4 wheels forward/backward**...

👉 check out this chapter:  
🔗 [L298N Motor Driver with 4 Wheels](L298N-Motor.md)
