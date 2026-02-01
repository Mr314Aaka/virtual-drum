import pygame
import numpy as np
import serial
import threading
import time
import sys

# --- CONFIGURATION ---
SAMPLE_RATE = 44100
WIDTH, HEIGHT = 800, 400
SERIAL_PORT = '/dev/ttyUSB0' # Ensure this matches your port
BAUD_RATE = 115200

# --- SOUND ENGINE ---

def generate_hybrid_snare():
    """
    NEW: Mixes a 'Shell' tone with 'Wire' noise for a realistic Snare.
    This creates that 'Thwack' sound instead of just a 'boing'.
    """
    n_samples = 20000 # ~0.5 seconds
    
    # LAYER 1: The Drum Shell (Tonal Body)
    # Uses a longer wavetable for a deeper pitch (approx 200Hz)
    wavetable_size = 250 
    wavetable = np.random.uniform(-1, 1, wavetable_size).astype(np.float32)
    shell_sound = np.zeros(n_samples, dtype=np.float32)
    ring_buf = list(wavetable)

    for i in range(n_samples):
        shell_sound[i] = ring_buf[0]
        # Low pass filter for the thud
        avg = 0.5 * (ring_buf[0] + ring_buf[1])
        ring_buf.pop(0)
        ring_buf.append(avg * 0.990) # Moderate decay

    # LAYER 2: The Snares (White Noise Burst)
    noise = np.random.uniform(-1, 1, n_samples).astype(np.float32)
    # Fast exponential decay envelope for the "Snap"
    envelope = np.exp(-np.linspace(0, 40, n_samples)) 
    wires_sound = noise * envelope

    # MIXING: Blend 50% Shell + 50% Wires
    combined = (shell_sound * 0.5) + (wires_sound * 0.5)

    # FINAL POLISH: Boost Highs for crispness
    # Simple difference filter
    final_sound = np.zeros(n_samples, dtype=np.float32)
    for i in range(1, n_samples):
        final_sound[i] = combined[i] - 0.5 * combined[i-1]

    # Normalize
    final_sound = final_sound / (np.max(np.abs(final_sound)) + 1e-6)
    return (final_sound * 32767).astype(np.int16)

def generate_tad_dhus_cymbal(is_open=False):
    """Tad-Dhus Cymbal (Keep existing)"""
    duration = 0.6 if is_open else 0.35 
    n_samples = int(SAMPLE_RATE * duration)
    buffer_lengths = [31, 37, 41, 83, 97] 
    weights = [0.3, 0.2, 0.3, 0.15, 0.15]
    combined_sound = np.zeros(n_samples, dtype=np.float32)

    for i, buf_len in enumerate(buffer_lengths):
        wavetable = np.random.uniform(-1, 1, buf_len).astype(np.float32)
        layer = np.zeros(n_samples, dtype=np.float32)
        ring_buf = list(wavetable)
        decay = (0.992 if buf_len > 50 else 0.980) if is_open else 0.95

        for j in range(n_samples):
            layer[j] = ring_buf[0]
            new_val = -ring_buf[0] * decay 
            ring_buf.pop(0)
            ring_buf.append(new_val)
        combined_sound += layer * weights[i]

    final_sound = np.zeros(n_samples, dtype=np.float32)
    for i in range(1, n_samples):
        final_sound[i] = combined_sound[i] - 0.6 * combined_sound[i-1]
    if not is_open: final_sound *= 1.5 
    final_sound = final_sound / (np.max(np.abs(final_sound)) + 1e-6)
    return (final_sound * 32767).astype(np.int16)

def generate_pro_kick():
    """Deep Kick (Keep existing)"""
    length = 20000
    wavetable = np.random.uniform(-1, 1, 150).astype(np.float32)
    for i in range(150): wavetable[i] *= (1.0 - (i/150)*0.3)
    raw = np.zeros(length, dtype=np.float32)
    buf = list(wavetable)
    for i in range(length):
        raw[i] = buf[0]
        avg = 0.5 * (buf[0] + buf[1])
        if np.random.randint(0,2): avg = -avg
        buf.pop(0)
        buf.append(avg * 0.995)
    window = np.ones(120)/120 
    final = np.convolve(raw, window, mode='same')
    return (final/np.max(np.abs(final)) * 32767).astype(np.int16)

# --- INITIALIZATION ---
pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 1024)
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("ESP32 Air Drums (Hybrid Snare Update)")

print("Synthesizing New Snare & Cymbals...")

# MAPPING
raw_sounds = {
    1: (generate_hybrid_snare(), (80, 255, 80), "HYBRID SNARE"),
    2: (generate_pro_kick(), (255, 80, 80), "KICK"),
    3: (generate_tad_dhus_cymbal(False), (255, 255, 100), "CLOSED HAT"),
    4: (generate_tad_dhus_cymbal(True), (255, 200, 0), "OPEN HAT")
}

current_wf = np.zeros(1000)
wf_color = (100, 100, 100)
label_text = "Waiting for Sticks..."
open_hat_channel = None

# --- SERIAL LISTENER WITH COOLDOWN ---
def serial_thread():
    global current_wf, wf_color, label_text, open_hat_channel
    print(f"Opening {SERIAL_PORT}...")
    
    # Cooldown Dictionary to stop spamming
    # Stores last hit time for each Stick ID
    last_hit_time = {1: 0, 2: 0, 3: 0, 4: 0}
    COOLDOWN = 0.08 # Minimum 80ms between hits
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
        print(f"SUCCESS: Connected to {SERIAL_PORT}")
        
        while True:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                if ":" in line:
                    parts = line.split(":")
                    if len(parts) == 2:
                        try:
                            stick_id = int(parts[0])
                            intensity = int(parts[1])
                            
                            # --- SPAM PROTECTION ---
                            now = time.time()
                            if stick_id in last_hit_time:
                                if (now - last_hit_time[stick_id]) < COOLDOWN:
                                    continue # Skip this hit (it's spam)
                                last_hit_time[stick_id] = now
                            
                            print(f"[HIT] ID: {stick_id}, Force: {intensity}")

                            if stick_id in raw_sounds:
                                raw_data, color, name = raw_sounds[stick_id]
                                
                                # Volume Scaling
                                vol_factor = max(0.2, intensity / 255.0) 
                                scaled_sound = (raw_data * vol_factor).astype(np.int16)
                                sound_obj = pygame.sndarray.make_sound(scaled_sound)
                                
                                if stick_id == 3: # Closed Hat Choke
                                    if open_hat_channel: open_hat_channel.stop()
                                    sound_obj.play()
                                elif stick_id == 4: 
                                    open_hat_channel = sound_obj.play()
                                else:
                                    sound_obj.play()

                                current_wf = scaled_sound[:1000]
                                wf_color = color
                                label_text = f"{name} (Vel: {intensity})"
                                
                        except ValueError:
                            pass
            except Exception as e:
                print(f"Serial Error: {e}")
                time.sleep(1) # Wait before retrying
                
    except Exception as e:
        print(f"[FATAL] Could not open port: {e}")

t = threading.Thread(target=serial_thread, daemon=True)
t.start()

# --- MAIN LOOP ---
running = True
clock = pygame.time.Clock()
font = pygame.font.SysFont('Arial', 24)

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        
        if event.type == pygame.KEYDOWN:
            # Test keys
            sim_id = None
            if event.key == pygame.K_s: sim_id = 1 # Test New Snare
            if event.key == pygame.K_a: sim_id = 2 
            if event.key == pygame.K_f: sim_id = 3 
            
            if sim_id:
                raw_data, color, name = raw_sounds[sim_id]
                pygame.sndarray.make_sound(raw_data).play()
                current_wf = raw_data[:1000]
                wf_color = color
                label_text = f"{name} (Key Test)"

    screen.fill((20, 20, 25))
    if np.any(current_wf):
        points = []
        for x in range(len(current_wf)):
            screen_x = int(x * (WIDTH / len(current_wf)))
            screen_y = int(HEIGHT/2 + (current_wf[x] / 32767) * 200)
            points.append((screen_x, screen_y))
        if len(points) > 1:
            pygame.draw.lines(screen, wf_color, False, points, 3)

    text = font.render(label_text, True, wf_color)
    screen.blit(text, (20, 20))
    pygame.display.flip()
    clock.tick(60)

pygame.quit()