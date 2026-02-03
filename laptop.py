import pygame
import numpy as np
import serial
import threading
import time
import sys

# --- CONFIGURATION ---
SAMPLE_RATE = 44100
WIDTH, HEIGHT = 800, 400
SERIAL_PORT = '/dev/ttyUSB0' # Ensure this matches your Receiver port
BAUD_RATE = 115200

# --- SOUND ENGINE GENERATORS ---

def generate_punchy_snare():
    """Synthesizes a high-impact Snare with a 'Pop' transient and high-pass noise."""
    n_samples = 20000
    t = np.linspace(0, n_samples / SAMPLE_RATE, n_samples)
    
    # 1. THE "POP" (Shell fundamental)
    freq_env = 180 + 220 * np.exp(-150 * t) 
    phase = 2 * np.pi * np.cumsum(freq_env) / SAMPLE_RATE
    pop = np.sin(phase) * np.exp(-30 * t) 

    # 2. THE "SNAP" (Initial stick contact)
    snap = np.random.uniform(-1, 1, n_samples) * np.exp(-800 * t)

    # 3. THE "SIZZLE" (Snare Wires via High-Pass Filter)
    noise = np.random.uniform(-1, 1, n_samples)
    wire_envelope = np.exp(-15 * t)
    sizzle = np.zeros(n_samples)
    for i in range(1, n_samples):
        sizzle[i] = (noise[i] - noise[i-1]) * wire_envelope[i]

    # Mix: 40% Shell, 20% Snap, 40% Wires
    combined = (pop * 0.4) + (snap * 0.2) + (sizzle * 0.4)
    combined = np.tanh(combined * 1.5) # Soft saturation for grit

    final_sound = combined / (np.max(np.abs(combined)) + 1e-6)
    return (final_sound * 32767 * 1.4).astype(np.int16)

def generate_pro_kick():
    """Deep membrane thump for the Kick drum."""
    length = 20000
    wavetable = np.random.uniform(-1, 1, 150).astype(np.float32)
    raw = np.zeros(length, dtype=np.float32)
    buf = list(wavetable)
    for i in range(length):
        raw[i] = buf[0]
        avg = 0.5 * (buf[0] + buf[1])
        if np.random.randint(0,2): avg = -avg
        buf.pop(0); buf.append(avg * 0.995)
    
    final = np.convolve(raw, np.ones(120)/120, mode='same')
    final = final / (np.max(np.abs(final)) + 1e-6)
    return (final * 32767 * 1.8).astype(np.int16)

def generate_pro_closed_hat():
    """Tight metallic 'Tad' chirp."""
    duration = 0.08
    n_samples = int(44100 * duration)
    buffer_lengths = [31, 41, 67]
    combined = np.zeros(n_samples, dtype=np.float32)
    for b_len in buffer_lengths:
        ring_buf = list(np.random.uniform(-1, 1, b_len))
        layer = np.zeros(n_samples)
        for j in range(n_samples):
            layer[j] = ring_buf[0]
            new_val = -ring_buf[0] * 0.92 
            ring_buf.pop(0); ring_buf.append(new_val)
        combined += layer * 0.33
    final = np.zeros(n_samples)
    for i in range(1, n_samples):
        final[i] = (combined[i] - combined[i-1]) * np.exp(-20 * (i/44100))
    return (final / (np.max(np.abs(final)) + 1e-6) * 32767 * 1.2).astype(np.int16)

def generate_pro_open_hat():
    """Shimmering 'Dhus' metallic wash."""
    duration = 0.8
    n_samples = int(44100 * duration)
    t = np.linspace(0, duration, n_samples)
    buffer_lengths = [31, 47, 61, 89, 113]
    combined = np.zeros(n_samples, dtype=np.float32)
    for b_len in buffer_lengths:
        ring_buf = list(np.random.uniform(-1, 1, b_len))
        layer = np.zeros(n_samples)
        for j in range(n_samples):
            layer[j] = ring_buf[0]
            new_val = -ring_buf[0] * 0.996
            ring_buf.pop(0); ring_buf.append(new_val)
        combined += layer * 0.2
    out = np.zeros(n_samples)
    shimmer = 1.0 + 0.2 * np.sin(2 * np.pi * 10 * t)
    for i in range(1, n_samples):
        out[i] = (combined[i] - 0.9 * combined[i-1]) * np.exp(-6 * t[i]) * shimmer[i]
    return (out / (np.max(np.abs(out)) + 1e-6) * 32767 * 1.3).astype(np.int16)

# --- INITIALIZATION ---
pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Air Drum Engine - Pro Snare Update")

print("Synthesizing Kit...")
raw_sounds = {
    1: (generate_punchy_snare(), (80, 255, 150), "SNARE"),
    2: (generate_pro_kick(), (255, 80, 80), "KICK"),
    3: (generate_pro_closed_hat(), (255, 255, 100), "CLOSED HAT"),
    4: (generate_pro_open_hat(), (255, 200, 0), "OPEN HAT")
}

current_wf = np.zeros(1000)
wf_color = (100, 100, 100)
label_text = "Waiting for Sticks..."
open_hat_channel = None

# --- SERIAL LISTENER THREAD ---
def serial_thread():
    global current_wf, wf_color, label_text, open_hat_channel
    last_hit_time = {1: 0, 2: 0, 3: 0, 4: 0}
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
        print(f"CONNECTED to {SERIAL_PORT}")
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if ":" in line:
                try:
                    sid, intensity = map(int, line.split(":"))
                    now = time.time()
                    if (now - last_hit_time.get(sid, 0)) > 0.08:
                        if sid in raw_sounds:
                            raw_data, color, name = raw_sounds[sid]
                            vol = max(0.3, (intensity / 255.0) ** 0.7)
                            sound_obj = pygame.sndarray.make_sound(raw_data)
                            
                            if sid == 3: # Hi-hat choke logic
                                if open_hat_channel: open_hat_channel.stop()
                                sound_obj.set_volume(vol); sound_obj.play()
                            elif sid == 4:
                                open_hat_channel = sound_obj.play()
                                if open_hat_channel: open_hat_channel.set_volume(vol)
                            else:
                                sound_obj.set_volume(vol); sound_obj.play()

                            current_wf = (raw_data[:1000] * vol).astype(np.int16)
                            wf_color = color
                            label_text = f"{name} (Vel: {intensity})"
                            last_hit_time[sid] = now
                except ValueError: pass
    except Exception as e: print(f"Serial Error: {e}")

threading.Thread(target=serial_thread, daemon=True).start()

# --- MAIN LOOP ---
clock = pygame.time.Clock()
font = pygame.font.SysFont('Arial', 24)

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: pygame.quit(); sys.exit()

    screen.fill((15, 15, 20))
    if np.any(current_wf):
        points = [(int(x*(WIDTH/1000)), int(HEIGHT/2 + (current_wf[x]/32767)*200)) for x in range(1000)]
        if len(points) > 1: pygame.draw.lines(screen, wf_color, False, points, 2)

    screen.blit(font.render(label_text, True, wf_color), (20, 20))
    pygame.display.flip()
    clock.tick(60)