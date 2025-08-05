
## 🗣️ Offline Voice Recognition (Vosk)

This chapter introduces the **"Voice Control"** mode, powered by **Vosk** — an awesome **offline speech recognition toolkit**. 🎧

Vosk supports more than **20 languages and dialects**, including:

🇬🇧 English, 🇩🇪 German, 🇫🇷 French, 🇪🇸 Spanish, 🇨🇳 Chinese, 🇷🇺 Russian, 🇯🇵 Japanese, 🇮🇳 Indian English, and more!

But the **best part?** You don’t need the internet! It runs entirely **offline** on your Raspberry Pi 5 — perfect for mobile projects like this smart car 🚗📦.

---

## 🧠 Voice Command Workflow

Here’s how it works in simple steps:

1. 🎤 You speak into the **Logitech Brio 100** webcam microphone.
2. 📥 The Pi 5 captures your voice.
3. 🤖 Vosk processes and turns it into **text**.
4. 🧠 The system matches words like `"front"`, `"back"`, `"left"`, `"right"`, or `"stop"`.
5. ⚙️ The car executes the action (like moving forward)!

🧩 Here's a mind map that visualizes the process:

![Mindmap of Voice Recognition Process](images/vosk_mindmap.jpg)

🔗 If you're curious about how to install Vosk, visit the official site: [https://alphacephei.com/vosk/](https://alphacephei.com/vosk/)

---

## ⚙️ Code Overview

Let's walk through the key parts of the code that make this voice control system work:

---

### 🔧 Step 1: Initialization and Setup

This part loads the Vosk model and sets the **microphone input** to use Logitech Brio 100 (usually index 0).

```python
# --- Vosk Speech Recognition Setup ---
VOSK_MODEL_PATH = "/home/jacky/models/vosk-model-small-en-us-0.15"
VOSK_MIC_INDEX = 0

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
```

🎤 Make sure your microphone is detected as index `0` — otherwise, the Pi might use the wrong input!

---

### 🧵 Step 2: Voice Listening Thread

This function **continuously listens** for your voice and converts the result into commands.

```python
def vosk_listen_thread():
    while True:
        if speech_active and vosk_recognizer and audio_stream and audio_stream.is_active():
            try:
                data = audio_stream.read(4000, exception_on_overflow=False)
                if vosk_recognizer.AcceptWaveform(data):
                    result = json.loads(vosk_recognizer.Result())
                    text = result.get('text', '').lower()
                    print(f"Recognized: '{text}'")

                    # Map text to actual commands
                    if text in ["front", "far"]:
                        command = "front"
                    elif text in ["back", "sack"]:
                        command = "back"
                    elif text in ["left", "net", "laugh", "less"]:
                        command = "left"
                    elif text in ["right", "write"]:
                        command = "right"
                    elif text == "stop":
                        command = "stop"
                    else:
                        command = None

                    if command:
                        print(f"Executing: {command}")
                        execute_timed_command(command)
                        speech_history_queue.queue.clear()
                        speech_history_queue.put(command)
                    else:
                        print(f"Ignored unknown: '{text}'")
```

🧠 It even handles **misheard** words — like turning `"laugh"` or `"net"` into `"left"` — so it’s more forgiving!

---

### 📋 Known Word Mappings

Here’s how your code interprets similar-sounding words:

| 🎤 Heard Words                 | 🧭 Mapped To |
| ------------------------------ | ------------ |
| `front`, `far`                 | `"front"`    |
| `back`, `sack`                 | `"back"`     |
| `left`, `net`, `laugh`, `less` | `"left"`     |
| `right`, `write`               | `"right"`    |
| `stop`                         | `"stop"`     |

✅ This helps with pronunciation mistakes or background noise!

---

### ⏱️ Step 3: Timed Command Execution

This function runs the actual movement, then stops after a short delay:

```python
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
```

⏳ Most actions run for **2 seconds** and then automatically stop — unless you say `"stop"` directly!

---

### 🧼 Cleanup (When Switching Modes)

If you’re switching away from voice control, don’t forget to clean up Vosk resources:

```python
def deinit_vosk():
    if audio_stream:
        audio_stream.stop_stream()
        audio_stream.close()
    if p_audio:
        p_audio.terminate()
    vosk_recognizer = None
    vosk_model = None
    print("Vosk de-initialized.")
```

---

### 🎙️ Voice Command Actions Summary

* **When you say "front" or "far":**

  * 🚗 The car moves forward
  * 💡 Front green LEDs turn ON
  * 👀 Great for moving straight ahead!
    [GIF Link: Car moving forward via voice](https://example.com/voice_front.gif)

* **When you say "back" or "sack":**

  * 🚗 The car moves backward
  * 💡 Rear red LEDs turn ON
  * 👀 Perfect for reversing safely!
    [GIF Link: Car moving backward via voice](https://example.com/voice_back.gif)

* **When you say "left", "net", "laugh", or "less":**

  * 🔄 The car turns left
  * 💡 All LEDs stay OFF
  * 👀 Helpful for turning at corners!
    [GIF Link: Car turning left via voice](https://example.com/voice_left.gif)

* **When you say "right" or "write":**

  * 🔄 The car turns right
  * 💡 All LEDs stay OFF
  * 👀 Smooth steering in tight spaces!
    [GIF Link: Car turning right via voice](https://example.com/voice_right.gif)

---

## 🔚 Final Notes

* 🎤 The **Logitech webcam’s built-in mic** makes voice control plug-and-play!
* 🧠 No internet needed — Vosk handles everything **offline**.
* 👂 Slight mispronunciations? No problem — the system is smart enough to guess!

---

📌 If you want to understand how the microphone is set up, check out [Logitech Webcam Microphone (used for Vosk)](Logitech_Webcam_Microphone.md) for hardware details.

