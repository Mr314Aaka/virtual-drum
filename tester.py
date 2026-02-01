import pygame
import numpy as np

# --- CONFIGURATION ---
SAMPLE_RATE = 44100
WIDTH, HEIGHT = 800, 400

def generate_tad_dhus_cymbal(is_open=False):
    """Synthesizes 'Tad-Dhus' Cymbal (Attack + Ring)"""
    duration = 0.6 if is_open else 0.35 
    n_samples = int(SAMPLE_RATE * duration)
    
    # Cluster Frequencies: Highs (31,37,41) + Body/Dhus (83,97)
    buffer_lengths = [31, 37, 41, 83, 97] 
    weights = [0.3, 0.2, 0.3, 0.15, 0.15]
    
    combined_sound = np.zeros(n_samples, dtype=np.float32)

    for i, buf_len in enumerate(buffer_lengths):
        wavetable = np.random.uniform(-1, 1, buf_len).astype(np.float32)
        layer = np.zeros(n_samples, dtype=np.float32)
        ring_buf = list(wavetable)
        
        if is_open:
            decay = 0.992 if buf_len > 50 else 0.980 
        else:
            decay = 0.95

        for j in range(n_samples):
            layer[j] = ring_buf[0]
            new_val = -ring_buf[0] * decay # High-Pass Feedback
            ring_buf.pop(0)
            ring_buf.append(new_val)
            
        combined_sound += layer * weights[i]

    # Filter: Allow some body (0.6 coeff) for the "Dhus" sound
    final_sound = np.zeros(n_samples, dtype=np.float32)
    for i in range(1, n_samples):
        final_sound[i] = combined_sound[i] - 0.6 * combined_sound[i-1]

    if not is_open: final_sound *= 1.5 # Boost closed hat
    
    final_sound = final_sound / (np.max(np.abs(final_sound)) + 1e-6)
    return (final_sound * 32767).astype(np.int16)

def generate_pro_kick():
    """Deep Kick"""
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
        
    window = np.ones(120)/120 # Heavy LPF
    final = np.convolve(raw, window, mode='same')
    return (final/np.max(np.abs(final)) * 32767).astype(np.int16)

def generate_pro_snare():
    """Crisp Snare"""
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
        buf.append(avg * 0.99)
        
    window = np.ones(12)/12 # Light LPF
    final = np.convolve(raw, window, mode='same')
    return (final/np.max(np.abs(final)) * 32767).astype(np.int16)

# --- INITIALIZATION ---
pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 1024)
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Visual Cymbal Engine")

print("Synthesizing...")
# Format: (SoundArray, Color, Label)
sounds_data = {
    pygame.K_a: (generate_pro_kick(), (255, 80, 80), "KICK"),
    pygame.K_s: (generate_pro_snare(), (80, 255, 80), "SNARE"),
    pygame.K_f: (generate_tad_dhus_cymbal(False), (255, 255, 100), "CLOSED HAT"), 
    pygame.K_g: (generate_tad_dhus_cymbal(True), (255, 200, 0), "OPEN HAT")   
}
# Create playable Sound objects
sounds = {k: pygame.sndarray.make_sound(v[0]) for k, v in sounds_data.items()}

# Graph Variables
current_wf = np.zeros(1000)
wf_color = (100, 100, 100)
label_text = "Ready"
open_hat = None

print("Ready! A=Kick, S=Snare, F=Closed, G=Open")

# --- MAIN LOOP ---
running = True
clock = pygame.time.Clock()
font = pygame.font.SysFont('Arial', 24)

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        if event.type == pygame.KEYDOWN and event.key in sounds:
            
            # Choke Logic
            if event.key == pygame.K_f:
                if open_hat: open_hat.stop()
                sounds[event.key].play()
            elif event.key == pygame.K_g:
                open_hat = sounds[event.key].play()
            else:
                sounds[event.key].play()
            
            # --- UPDATE GRAPH DATA ---
            # Grab the first 1000 samples for the visualizer
            current_wf = sounds_data[event.key][0][:1000]
            wf_color = sounds_data[event.key][1]
            label_text = sounds_data[event.key][2]

    # Draw Background
    screen.fill((20, 20, 25))
    
    # Draw Waveform
    if np.any(current_wf):
        # Scale X to width, Y to height/2
        points = []
        for x in range(len(current_wf)):
            screen_x = int(x * (WIDTH / len(current_wf)))
            # Multiply by 200 to scale amplitude visually
            screen_y = int(HEIGHT/2 + (current_wf[x] / 32767) * 200)
            points.append((screen_x, screen_y))
        
        if len(points) > 1:
            pygame.draw.lines(screen, wf_color, False, points, 3)

    # Draw Label
    text = font.render(label_text, True, wf_color)
    screen.blit(text, (20, 20))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()