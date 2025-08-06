# 🎙️ Logitech Webcam Microphone (Used for Vosk)

This chapter introduces the **Logitech Brio 100 Webcam**, a key hardware component in the voice recognition system of your Raspberry Pi 5 smart car project.

🔌 It’s a **USB webcam** — simply plug it into one of the USB ports on your Raspberry Pi 5, and you're good to go.  
It **streams live video** for the web interface and also provides a **built-in microphone**, perfect for offline voice control with Vosk.

---

### 🖼️ Webcam Hardware Overview

Here’s what the Logitech Brio 100 Webcam looks like:

![Logitech Webcam Brio 100](assets/logitech_webcam.jpg)

The beauty of this device is that it’s **all-in-one** — no need to buy a separate microphone!  
Just one device for both **camera streaming** and **voice input**.

---

### ⚙️ Microphone Device Setup

Before diving into the actual voice control features using Vosk, here’s how the microphone is configured in the code.

The microphone device is selected using this line:

```python
VOSK_MIC_INDEX = 0  # Fixed microphone input index
```
This line tells the Raspberry Pi 5 to use the first available microphone input.
If your Logitech Brio 100 is plugged in correctly, it should automatically be assigned index 0.

---

### 🛠️ Important Tip:

If this index changes (for example, after a reboot or if you plug in another audio device), the Vosk speech recognition might stop working.

➡️ To double-check your audio input devices, run the following command in the terminal:

```python
arecord -l
```
This will list all available audio devices so you can verify which index corresponds to the webcam mic.

---

📎 If you're interested in **how the offline voice recognition system (Vosk) works**,  
**how voice commands are processed to control the car**,  

👉 check out this chapter:  
🔗 [Offline Voice Recognition(Vosk)](Offline_Voice_Recognition_Vosk.md)
