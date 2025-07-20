from flask import Flask, Response, render_template_string, request, jsonify
from gpiozero import DigitalOutputDevice, PWMOutputDevice, DistanceSensor
import cv2
import threading
import time
from evdev import InputDevice, categorize, ecodes
from evdev import list_devices
import pyaudio
from vosk import Model, KaldiRecognizer, SetLogLevel
import json
import queue
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# --- Vosk Speech Recognition Setup ---
VOSK_MODEL_PATH = "/home/jacky/models/vosk-model-small-en-us-0.15"
VOSK_MIC_INDEX = 0

vosk_model = None
vosk_recognizer = None
p_audio = None
audio_stream = None
speech_active = False
speech_history_queue = queue.Queue(maxsize=1)
COMMAND_DURATION = 2

KNOWN_COMMANDS = [
    "front", "back", "left", "right", "stop",
    "net", "laugh", "less", "write", "far", "sack"
]

# --- GPIO Pin Definitions ---
ENA_GPIO = 24
IN1_GPIO = 17
IN2_GPIO = 27
ENB_GPIO = 25
IN3_GPIO = 22
IN4_GPIO = 23
TRIGGER_PIN = 16  # HC-SR04 Trigger
ECHO_PIN = 26     # HC-SR04 Echo
BUZZER_PIN = 6    # Active Buzzer
GREEN_LED1_PIN = 20  # Front green LED 1
GREEN_LED2_PIN = 21  # Front green LED 2
RED_LED1_PIN = 2     # Back red LED 1
RED_LED2_PIN = 3     # Back red LED 2

# --- Initialize GPIO Zero Devices ---
in1 = DigitalOutputDevice(IN1_GPIO)
in2 = DigitalOutputDevice(IN2_GPIO)
ena = PWMOutputDevice(ENA_GPIO)
in3 = DigitalOutputDevice(IN3_GPIO)
in4 = DigitalOutputDevice(IN4_GPIO)
enb = PWMOutputDevice(ENB_GPIO)
distance_sensor = DistanceSensor(echo=ECHO_PIN, trigger=TRIGGER_PIN, max_distance=4)  # Max distance in meters
buzzer = DigitalOutputDevice(BUZZER_PIN)
green_led1 = DigitalOutputDevice(GREEN_LED1_PIN)
green_led2 = DigitalOutputDevice(GREEN_LED2_PIN)
red_led1 = DigitalOutputDevice(RED_LED1_PIN)
red_led2 = DigitalOutputDevice(RED_LED2_PIN)

# --- Speed Constants ---
MAX_PWM_SPEED = 1.0
BASE_SPEED = 0.4
TURN_SPEED = 1.0
TURN_DURATION = 0.9
STOP_DURATION_AFTER_TURN = 6.8
STOP_DURATION_VICTORY = 8.0

# --- States for Gesture Control ---
STATE_FORWARD = 'forward'
STATE_TURNING_LEFT = 'turning_left'
STATE_TURNING_RIGHT = 'turning_right'
STATE_STOPPED = 'stopped'

# --- Global Variables ---
current_control_mode = 'ipad_buttons'
controller_active = False
speech_active = False
gesture_active = False
current_gesture_command = "none"
gesture_recognizer = None
nintendo_controller = None
obstacle_detection_active = False
obstacle_warning = False

# --- Camera Setup ---
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# --- Mediapipe Setup ---
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_hands = mp.solutions.hands

def init_gesture_recognizer():
    global gesture_recognizer
    model_path = "/home/jacky/mediapipe-samples/examples/gesture_recognizer/raspberry_pi/gesture_recognizer.task"
    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.GestureRecognizerOptions(base_options=base_options,
                                              running_mode=vision.RunningMode.IMAGE,
                                              num_hands=1,
                                              min_hand_detection_confidence=0.5,
                                              min_hand_presence_confidence=0.5,
                                              min_tracking_confidence=0.5)
    gesture_recognizer = vision.GestureRecognizer.create_from_options(options)

init_gesture_recognizer()

# --- Motor Control Functions ---
def move_forward(speed):
    in1.on(); in2.off()
    in3.off(); in4.on()
    ena.value = speed
    enb.value = speed
    green_led1.on()
    green_led2.on()
    print(f"Action: Forward at {speed:.2f}")

def move_backward(speed):
    in1.off(); in2.on()
    in3.on(); in4.off()
    ena.value = speed
    enb.value = speed
    red_led1.on()
    red_led2.on()
    print(f"Action: Backward at {speed:.2f}")

def turn_left(speed):
    in1.on(); in2.off()
    in3.off(); in4.off()
    ena.value = speed
    enb.value = 0.0
    green_led1.off()
    green_led2.off()
    red_led1.off()
    red_led2.off()
    print(f"Action: Left (L:{speed:.2f}, R:0.0)")

def turn_right(speed):
    in1.off(); in2.off()
    in3.off(); in4.on()
    ena.value = 0.0
    enb.value = speed
    green_led1.off()
    green_led2.off()
    red_led1.off()
    red_led2.off()
    print(f"Action: Right (L:0.0, R:{speed:.2f})")

def stop_motors():
    in1.off(); in2.off()
    in3.off(); in4.off()
    ena.off()
    enb.off()
    green_led1.off()
    green_led2.off()
    red_led1.off()
    red_led2.off()
    print("Action: Stop")

# --- Timed Command Execution for Voice ---
def execute_timed_command(command):
    if current_control_mode != 'speech_recognition':
        return
    if command == "front":
        move_forward(MAX_PWM_SPEED)
    elif command == "back":
        move_backward(MAX_PWM_SPEED)
    elif command == "left":
        turn_left(MAX_PWM_SPEED)
    elif command == "right":
        turn_right(MAX_PWM_SPEED)
    elif command == "stop":
        stop_motors()
    if command != "stop":
        threading.Timer(COMMAND_DURATION, stop_motors).start()

# --- Obstacle Detection Thread ---
def obstacle_detection_thread():
    global obstacle_warning
    while True:
        if obstacle_detection_active:
            distance = distance_sensor.distance * 100  # Convert to cm
            if distance < 20:
                buzzer.on()  # Continuous beep
                obstacle_warning = True
            else:
                buzzer.off()
                obstacle_warning = False
        else:
            buzzer.off()
            obstacle_warning = False
        time.sleep(0.1)

obstacle_thread = threading.Thread(target=obstacle_detection_thread, daemon=True)
obstacle_thread.start()

# --- Gesture Recognition Thread ---
def gesture_recognition_thread():
    global current_gesture_command
    while True:
        if gesture_active:
            success, frame = camera.read()
            if success:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                result = gesture_recognizer.recognize(mp_image)
                if result.gestures:
                    category_name = result.gestures[0][0].category_name
                    if category_name == "Thumb_Up":
                        current_gesture_command = "turn_left"
                    elif category_name == "Thumb_Down":
                        current_gesture_command = "turn_right"
                    elif category_name == "Victory":
                        current_gesture_command = "stop"
                    else:
                        current_gesture_command = "none"
                else:
                    current_gesture_command = "none"
        time.sleep(0.1)

gesture_recognition_thread = threading.Thread(target=gesture_recognition_thread, daemon=True)
gesture_recognition_thread.start()

# --- Gesture Car Control Thread ---
def gesture_car_control_thread():
    current_state = STATE_STOPPED
    state_start_time = time.time()
    stop_duration = 0
    last_command = "none"

    while True:
        if gesture_active:
            command = current_gesture_command
            if current_state == STATE_FORWARD:
                if command != last_command and command != "none":
                    if command == "turn_left":
                        current_state = STATE_TURNING_LEFT
                        turn_left(TURN_SPEED)
                        state_start_time = time.time()
                        last_command = command
                    elif command == "turn_right":
                        current_state = STATE_TURNING_RIGHT
                        turn_right(TURN_SPEED)
                        state_start_time = time.time()
                        last_command = command
                    elif command == "stop":
                        current_state = STATE_STOPPED
                        stop_motors()
                        stop_duration = STOP_DURATION_VICTORY
                        state_start_time = time.time()
                        last_command = command
                else:
                    move_forward(BASE_SPEED)
            elif current_state == STATE_TURNING_LEFT:
                if time.time() - state_start_time >= TURN_DURATION:
                    current_state = STATE_STOPPED
                    stop_motors()
                    stop_duration = STOP_DURATION_AFTER_TURN
                    state_start_time = time.time()
            elif current_state == STATE_TURNING_RIGHT:
                if time.time() - state_start_time >= TURN_DURATION:
                    current_state = STATE_STOPPED
                    stop_motors()
                    stop_duration = STOP_DURATION_AFTER_TURN
                    state_start_time = time.time()
            elif current_state == STATE_STOPPED:
                if time.time() - state_start_time >= stop_duration:
                    current_state = STATE_FORWARD
                    move_forward(BASE_SPEED)
        time.sleep(0.1)

gesture_control_thread = threading.Thread(target=gesture_car_control_thread, daemon=True)
gesture_control_thread.start()

# --- Controller Thread ---
controller_state = {
    'forward': False,
    'backward': False,
    'left': False,
    'right': False
}

def find_pro_controller():
    found_controller = None
    found_imu_controller = None
    for path in list_devices():
        try:
            device = InputDevice(path)
            if "Pro Controller (IMU)" in device.name and "Pro Controller" in device.name:
                found_imu_controller = device
            elif "Pro Controller" in device.name:
                print(f"Found primary Nintendo Switch Pro Controller: {device.name} at {device.path}")
                return device
            else:
                device.close()
        except OSError as e:
            print(f"Warning: Could not open device {path} - {e}")
            continue
    if found_imu_controller:
        print(f"Found Pro Controller (IMU) as fallback: {found_imu_controller.name} at {found_imu_controller.path}")
        return found_imu_controller
    return None

def read_controller_input():
    global nintendo_controller, controller_active
    while True:
        if nintendo_controller is None:
            print("Attempting to find Pro Controller...")
            nintendo_controller = find_pro_controller()
            if nintendo_controller is None:
                print("Pro Controller not found. Retrying in 3 seconds...")
                stop_motors()
                time.sleep(3)
                continue

        try:
            print(f"Starting read loop for: {nintendo_controller.name} at {nintendo_controller.path}")
            for event in nintendo_controller.read_loop():
                if not controller_active:
                    stop_motors()
                    continue

                if event.type == ecodes.EV_KEY:
                    if event.code == 313:  # ZR
                        controller_state['forward'] = (event.value == 1)
                    elif event.code == 312:  # ZL
                        controller_state['backward'] = (event.value == 1)
                elif event.type == ecodes.EV_ABS:
                    if event.code == 16:  # D-pad Horizontal
                        if event.value == -1:  # Left
                            controller_state['left'] = True
                            controller_state['right'] = False
                        elif event.value == 1:  # Right
                            controller_state['right'] = True
                            controller_state['left'] = False
                        elif event.value == 0:  # Centered
                            controller_state['left'] = False
                            controller_state['right'] = False

                if controller_active:
                    if controller_state['forward']:
                        move_forward(MAX_PWM_SPEED)
                    elif controller_state['backward']:
                        move_backward(MAX_PWM_SPEED)
                    elif controller_state['left']:
                        turn_left(MAX_PWM_SPEED)
                    elif controller_state['right']:
                        turn_right(MAX_PWM_SPEED)
                    else:
                        stop_motors()
                else:
                    stop_motors()

        except FileNotFoundError:
            print(f"Error: Controller device {nintendo_controller.path if nintendo_controller else 'N/A'} disconnected during read_loop. Attempting to re-find.")
            nintendo_controller = None
            stop_motors()
            time.sleep(2)
        except Exception as e:
            print(f"An unexpected error occurred in controller input thread: {e}")
            nintendo_controller = None
            stop_motors()
            time.sleep(2)
        finally:
            if nintendo_controller is not None:
                try:
                    nintendo_controller.close()
                    print(f"Closed controller device {nintendo_controller.path}")
                except Exception as e:
                    print(f"Error closing controller device: {e}")
            nintendo_controller = None
            stop_motors()
            print("Controller input thread lost connection or encountered an issue. Re-attempting to find controller.")
            time.sleep(1)

controller_thread = threading.Thread(target=read_controller_input, daemon=True)
controller_thread.start()

# --- Speech Recognition Thread ---
def vosk_listen_thread():
    global vosk_recognizer, speech_active, audio_stream, speech_history_queue
    print("Vosk listening thread started.")
    while True:
        if speech_active and vosk_recognizer and audio_stream and audio_stream.is_active():
            try:
                data = audio_stream.read(4000, exception_on_overflow=False)
                if vosk_recognizer.AcceptWaveform(data):
                    result_full = vosk_recognizer.Result()
                    result = json.loads(result_full)
                    text = result.get('text', '').lower()
                    print(f"Vosk full result: {result_full}")
                    print(f"Vosk recognized text: '{text}'")

                    actual_command = None
                    if text in ["front", "far"]:
                        actual_command = "front"
                    elif text in ["back", "sack"]:
                        actual_command = "back"
                    elif text in ["left", "net", "laugh", "less"]:
                        actual_command = "left"
                    elif text in ["right", "write"]:
                        actual_command = "right"
                    elif text == "stop":
                        actual_command = "stop"

                    if actual_command:
                        print(f"Executing voice command (recognized as {text}, mapped to {actual_command})")
                        execute_timed_command(actual_command)
                        while not speech_history_queue.empty():
                            speech_history_queue.get_nowait()
                        speech_history_queue.put(actual_command)
                    else:
                        print(f"Ignoring unrecognized command: '{text}' (no mapping found)")
                else:
                    print("Vosk recognized empty text or no speech detected.")

            except Exception as e:
                print(f"CRITICAL ERROR in Vosk listening thread: {e}")
                deinit_vosk()
                init_vosk()
                time.sleep(1)
        else:
            time.sleep(0.1)

vosk_thread = threading.Thread(target=vosk_listen_thread, daemon=True)
vosk_thread.start()

# --- Flask App Routes ---
app = Flask(__name__)

html = """
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Raspberry Pi Car Control</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0; padding: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
      justify-content: space-between;
      position: relative;
      padding-bottom: env(safe-area-inset-bottom);
      padding-left: env(safe-area-inset-left);
      padding-right: env(safe-area-inset-right);
    }
    .top-section {
        width: 100%;
        text-align: center;
        padding-top: 10px;
    }
    .video-container {
      display: flex;
      justify-content: center;
      align-items: center;
      width: 100%;
      flex-grow: 1;
    }
    #camera {
      width: auto;
      max-width: 90%;
      height: 360px;
      aspect-ratio: 4 / 3;
      object-fit: contain;
      border-radius: 8px;
    }
    #ipadButtons {
        display: none;
        position: absolute;
        bottom: env(safe-area-inset-bottom);
        left: env(safe-area-inset-left);
        right: env(safe-area-inset-right);
        padding: 0;
        width: calc(100vw - env(safe-area-inset-left) - env(safe-area-inset-right));
        max-width: 1366px;
        margin: 0px 10px;
        box-sizing: border-box;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
    }
    .left-controls {
      display: flex;
      flex-direction: column;
      gap: 20px;
      margin-left: 0;
      align-items: flex-start;
    }
    .right-controls {
      display: flex;
      flex-direction: row;
      gap: 20px;
      margin-right: 0;
      align-items: flex-end;
    }
    button {
      width: 90px;
      height: 90px;
      font-size: 36px;
      border-radius: 50%;
      border: none;
      color: white;
      background-color: #04AA6D;
      box-shadow: 0 6px #666;
      cursor: pointer;
      flex-shrink: 0;
    }
    button:active {
      background-color: #3e8e41;
      box-shadow: 0 3px #444;
      transform: translateY(4px);
    }
    #speechHistoryBox {
        background-color: #f0f0f0;
        border: 1px solid #ccc;
        padding: 10px;
        margin-top: 10px;
        width: 90%;
        max-width: 600px;
        text-align: center;
        font-size: 1.2em;
        color: #333;
        min-height: 40px;
        display: none;
    }
    #obstacleWarningBox {
        display: none;
        border: 2px solid black;
        padding: 10px;
        margin-top: 10px;
        text-align: center;
        width: 90%;
        max-width: 600px;
    }
    #obstacleWarningText {
        color: red;
        font-size: 1.2em;
    }
  </style>
</head>
<body>
  <div class="top-section">
    <h2>Raspberry Pi Car Control</h2>
    <label for="controlMode">Control Mode:</label>
    <select id="controlMode" onchange="changeControlMode()">
      <option value="ipad_buttons">iPad Buttons</option>
      <option value="switch_controller">Switch Controller</option>
      <option value="speech_recognition">Voice Control</option>
      <option value="gesture_recognition">Gesture Recognition</option>
    </select>
    <p id="controllerStatus" style="color: red;"></p>
  </div>

  <div class="video-container">
    <img id="camera" src="/video_feed" />
  </div>

  <div id="obstacleWarningBox">
    <span id="obstacleWarningText"></span>
  </div>

  <div id="speechHistoryBox">Ready for command: Say 'front', 'back', 'left', 'right', or 'stop'</div>

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

  <script>
    let speechHistoryInterval;

    document.addEventListener('DOMContentLoaded', (event) => {
        const controlModeSelect = document.getElementById('controlMode');
        const savedMode = localStorage.getItem('controlMode') || 'ipad_buttons';
        controlModeSelect.value = savedMode;
        changeControlMode(true);
        setInterval(checkControllerStatus, 3000);
        checkControllerStatus();
        setInterval(updateObstacleWarning, 200);
    });

    function send(cmd) {
      fetch('/' + cmd);
    }

    function changeControlMode(isInitialLoad = false) {
        const selectedMode = document.getElementById('controlMode').value;
        const ipadButtonsDiv = document.getElementById('ipadButtons');
        const speechHistoryBox = document.getElementById('speechHistoryBox');
        const controllerStatusP = document.getElementById('controllerStatus');

        if (selectedMode === 'ipad_buttons') {
            ipadButtonsDiv.style.display = 'flex';
        } else {
            ipadButtonsDiv.style.display = 'none';
        }

        if (selectedMode === 'speech_recognition') {
            speechHistoryBox.style.display = 'block';
            speechHistoryBox.textContent = "Ready for command: Say 'front', 'back', 'left', 'right', or 'stop'";
            if (!speechHistoryInterval) {
                speechHistoryInterval = setInterval(updateSpeechHistory, 500);
            }
        } else {
            speechHistoryBox.style.display = 'none';
            if (speechHistoryInterval) {
                clearInterval(speechHistoryInterval);
                speechHistoryInterval = null;
            }
        }

        localStorage.setItem('controlMode', selectedMode);

        if (!isInitialLoad) {
            fetch('/set_control_mode?mode=' + selectedMode)
                .then(response => response.text())
                .then(data => {
                    console.log('Control mode set to:', selectedMode, 'Response:', data);
                    if (selectedMode === 'switch_controller') {
                        checkControllerStatus();
                    }
                })
                .catch(error => console.error('Error setting control mode:', error));
        }
    }

    function checkControllerStatus() {
        const controllerStatusP = document.getElementById('controllerStatus');
        fetch('/get_controller_status')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'connected') {
                    controllerStatusP.textContent = `Controller Connected: ${data.name}`;
                    controllerStatusP.style.color = 'green';
                } else {
                    controllerStatusP.textContent = 'Controller Not Connected or Not Found';
                    controllerStatusP.style.color = 'red';
                }
            })
            .catch(error => {
                console.error('Error checking controller status:', error);
                controllerStatusP.textContent = 'Error checking controller status.';
                controllerStatusP.style.color = 'red';
            });
    }

    let speechDisplayTimeout;
    function updateSpeechHistory() {
        const speechHistoryBox = document.getElementById('speechHistoryBox');
        fetch('/get_speech_history')
            .then(response => response.json())
            .then(data => {
                if (data.command && data.command !== speechHistoryBox.dataset.lastCommand) {
                    speechHistoryBox.textContent = data.command.charAt(0).toUpperCase() + data.command.slice(1);
                    speechHistoryBox.dataset.lastCommand = data.command;
                    if (speechDisplayTimeout) {
                        clearTimeout(speechDisplayTimeout);
                    }
                    speechDisplayTimeout = setTimeout(() => {
                        speechHistoryBox.textContent = "Ready for command: Say 'front', 'back', 'left', 'right', or 'stop'";
                        speechHistoryBox.dataset.lastCommand = '';
                    }, 2000);
                }
            })
            .catch(error => {
                console.error('Error fetching speech history:', error);
                speechHistoryBox.textContent = 'Speech system error.';
            });
    }

    function updateObstacleWarning() {
        fetch('/get_obstacle_status')
            .then(response => response.json())
            .then(data => {
                const obstacleWarningBox = document.getElementById('obstacleWarningBox');
                const obstacleWarningText = document.getElementById('obstacleWarningText');
                if (data.warning) {
                    obstacleWarningText.textContent = "Warning: Too Close!";
                    obstacleWarningBox.style.display = 'block';
                } else {
                    obstacleWarningBox.style.display = 'none';
                }
            })
            .catch(error => console.error('Error fetching obstacle status:', error));
    }
  </script>
</body>
</html>
"""

def gen_frames():
    with mp_hands.Hands(
        model_complexity=0,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as hands:
        while True:
            success, frame = camera.read()
            if not success:
                break
            if gesture_active:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb_frame)
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(
                            frame,
                            hand_landmarks,
                            mp_hands.HAND_CONNECTIONS,
                            mp_drawing_styles.get_default_hand_landmarks_style(),
                            mp_drawing_styles.get_default_hand_connections_style()
                        )
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return render_template_string(html)

@app.route('/forward')
def forward_route():
    if current_control_mode == 'ipad_buttons':
        move_forward(MAX_PWM_SPEED)
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

@app.route('/get_controller_status')
def get_controller_status():
    if nintendo_controller:
        return jsonify({'status': 'connected', 'name': nintendo_controller.name}), 200
    else:
        return jsonify({'status': 'disconnected', 'name': 'N/A'}), 200

@app.route('/get_speech_history')
def get_speech_history():
    if not speech_history_queue.empty():
        command = speech_history_queue.get_nowait()
        return jsonify({'command': command}), 200
    return jsonify({'command': None}), 200

@app.route('/get_obstacle_status')
def get_obstacle_status():
    return jsonify({'warning': obstacle_warning}), 200

@app.route('/set_control_mode')
def set_control_mode():
    global current_control_mode, controller_active, speech_active, gesture_active, obstacle_detection_active
    mode = request.args.get('mode')
    if mode in ['ipad_buttons', 'switch_controller', 'speech_recognition', 'gesture_recognition']:
        current_control_mode = mode
        stop_motors()
        if mode == 'switch_controller':
            controller_active = True
            speech_active = False
            gesture_active = False
            obstacle_detection_active = True
            print("Control mode set to Switch Controller.")
        elif mode == 'speech_recognition':
            controller_active = False
            speech_active = True
            gesture_active = False
            obstacle_detection_active = False
            deinit_vosk()
            init_vosk()
            print("Control mode set to Speech Recognition.")
        elif mode == 'gesture_recognition':
            controller_active = False
            speech_active = False
            gesture_active = True
            obstacle_detection_active = False
            print("Control mode set to Gesture Recognition.")
        else:  # ipad_buttons
            controller_active = False
            speech_active = False
            gesture_active = False
            obstacle_detection_active = True
            deinit_vosk()
            print("Control mode set to iPad Buttons.")
        buzzer.off()  # Ensure buzzer is off when switching modes
        return f"Control mode set to {mode}", 200
    return "Invalid mode", 400

def init_vosk():
    global vosk_model, vosk_recognizer, p_audio, audio_stream
    if not vosk_model:
        SetLogLevel(-1)
        vosk_model = Model(VOSK_MODEL_PATH)
        vosk_recognizer = KaldiRecognizer(vosk_model, 16000)
        p_audio = pyaudio.PyAudio()
        audio_stream = p_audio.open(format=pyaudio.paInt16, channels=1, rate=16000,
                                    input=True, input_device_index=VOSK_MIC_INDEX,
                                    frames_per_buffer=8000)
        audio_stream.start_stream()
        print("Vosk initialized.")

def deinit_vosk():
    global vosk_model, vosk_recognizer, p_audio, audio_stream
    if audio_stream:
        audio_stream.stop_stream()
        audio_stream.close()
        audio_stream = None
    if p_audio:
        p_audio.terminate()
        p_audio = None
    vosk_recognizer = None
    vosk_model = None
    print("Vosk de-initialized.")

if __name__ == '__main__':
    stop_motors()
    init_vosk()
    app.run(host='0.0.0.0', port=5000, threaded=True)

