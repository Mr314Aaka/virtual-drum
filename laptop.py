import pygame
import numpy as np
import serial
import threading
import time
import sys
import queue 

# --- CONFIGURATION ---
SAMPLE_RATE = 44100
WIDTH, HEIGHT = 800, 400
SERIAL_PORT = '/dev/ttyUSB0' # CHECK THIS!
BAUD_RATE = 115200

# --- QUEUE FOR THREAD SAFETY ---
sound_queue = queue.Queue()

# --- HIGH QUALITY SOUND GENERATORS ---

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
    combined = np.tanh(combined * 1.5) # Soft saturation
    
    # Normalize
    max_val = np.max(np.abs(combined))
    if max_val == 0: return np.zeros(n_samples, dtype=np.int16)
    return (combined / max_val * 32767 * 0.9).astype(np.int16)

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
    
    max_val = np.max(np.abs(final))
    if max_val == 0: return np.zeros(length, dtype=np.int16)
    return (final / max_val * 32767 * 0.95).astype(np.int16)

def generate_pro_closed_hat():
    """Acoustic Closed Hat - Tight metallic 'tick'"""
    duration = 0.08
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)
    
    # Metallic Cluster (9-11 kHz)
    metallic_freqs = [(9400, 0.35), (9700, 0.40), (10100, 0.50), (10400, 0.45), (10700, 0.38), (11200, 0.25)]
    metal = np.zeros(n_samples, dtype=np.float32)
    for freq, amp in metallic_freqs:
        detune = 1.0 + np.random.uniform(-0.002, 0.002)
        phase = np.random.uniform(0, 2 * np.pi)
        metal += amp * np.sin(2 * np.pi * freq * detune * t + phase)
    
    # Filtered Noise
    noise = np.random.uniform(-1, 1, n_samples).astype(np.float32)
    hp_noise = np.zeros(n_samples)
    for i in range(1, n_samples):
        hp_noise[i] = noise[i] - 0.75 * noise[i - 1]
    
    # Transient Click
    click_len = 80
    click = np.zeros(n_samples)
    click_env = np.exp(-np.linspace(0, 10, click_len))
    click[:click_len] = np.random.uniform(-1, 1, click_len) * click_env
    
    # Envelope
    envelope = np.exp(-400 * t) * 0.85 + np.exp(-60 * t) * 0.15
    
    # Mix
    combined = (metal * 0.50 + hp_noise * 0.25 + click * 0.40) * envelope
    
    # High Pass Clean & Saturation
    hp = np.zeros(n_samples)
    for i in range(1, n_samples):
        hp[i] = combined[i] - 0.985 * combined[i - 1]
    hp = np.tanh(hp * 1.4)
    
    max_val = np.max(np.abs(hp))
    if max_val == 0: return np.zeros(n_samples, dtype=np.int16)
    return (hp / max_val * 32767 * 0.8).astype(np.int16)

def generate_pro_open_hat():
    """Shimmering 'Dhus' metallic wash."""
    duration = 0.6 # Slightly shorter for better feel
    n_samples = int(SAMPLE_RATE * duration)
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
        
    max_val = np.max(np.abs(out))
    if max_val == 0: return np.zeros(n_samples, dtype=np.int16)
    return (out / max_val * 32767 * 0.8).astype(np.int16)

# --- INIT ---
# Increased buffer to 2048 to prevent Linux audio silence/glitches
pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 2048)
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Air Drums: Pro Engine")
font = pygame.font.SysFont('Arial', 24)

# Kit Mapping
print("Synthesizing PRO Sounds... please wait.")
# Mode 0: Snare (ID 2) & Kick (ID 1)
# Mode 1: Closed Hat (ID 2) & Open Hat (ID 1)
kits = {
    0: {2: (generate_punchy_snare(), (80,255,150), "SNARE"), 1: (generate_pro_kick(), (255,80,80), "KICK")},
    1: {2: (generate_pro_closed_hat(), (255,255,100), "CH"), 1: (generate_pro_open_hat(), (255,200,0), "OH")}
}
print("Sounds ready!")

# Play startup sound
startup_snd = pygame.sndarray.make_sound(kits[0][1][0])
startup_snd.set_volume(0.5)
startup_snd.play()

curr_wf, wf_col, label, active_mode = np.zeros(1000), (100,100,100), "Ready", 0
ch_handle = None

def serial_worker():
    try:
        print(f"Opening {SERIAL_PORT}...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        print("Serial Port Open! Waiting for data...")
        
        while True:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line: continue
                
                if line.count(':') == 2:
                    sid, intensity, mode = map(int, line.split(':'))
                    # Send valid data to the main thread via queue
                    sound_queue.put((sid, intensity, mode))
                    
            except ValueError:
                continue 
            except Exception as e:
                print(f"Read Error: {e}")
                
    except Exception as e: 
        print(f"CRITICAL SERIAL ERROR: {e}")
        print("Did you forget to close the Arduino Serial Monitor?")

threading.Thread(target=serial_worker, daemon=True).start()

# --- MAIN LOOP ---
clock = pygame.time.Clock()

while True:
    # 1. PROCESS SERIAL EVENTS
    while not sound_queue.empty():
        sid, intensity, mode = sound_queue.get()
        active_mode = mode
        
        if mode in kits and sid in kits[mode]:
            data, col, name = kits[mode][sid]
            
            # Volume Logic
            vol = (intensity/255.0)**0.7
            print(f"Playing: {name} (Vol: {vol:.2f})") 
            
            snd = pygame.sndarray.make_sound(data)
            snd.set_volume(vol)
            
            # CHOKE LOGIC: If Closed Hat (CH) plays, cut Open Hat (OH)
            if "CH" in name and ch_handle: 
                ch_handle.stop()
                
            h = snd.play()
            
            # Save handle if this is Open Hat, so we can cut it later
            if "OH" in name: 
                ch_handle = h
            
            curr_wf, wf_col, label = (data[:1000]*vol).astype(np.int16), col, f"KIT {mode}: {name}"

    # 2. DRAWING
    for e in pygame.event.get():
        if e.type == pygame.QUIT: pygame.quit(); sys.exit()
        
    screen.fill((10,10,15))
    if np.any(curr_wf):
        pts = [(int(i*(WIDTH/1000)), int(HEIGHT/2 + (curr_wf[i]/32767)*150)) for i in range(1000)]
        if len(pts) > 1:
            pygame.draw.lines(screen, wf_col, False, pts, 2)
            
    screen.blit(font.render(label, True, wf_col), (20,20))
    
    # Mode Indicator
    pygame.draw.circle(screen, (0,255,0) if active_mode==1 else (255,255,255), (WIDTH-30, 30), 10)
    
    pygame.display.flip()
    clock.tick(60)
