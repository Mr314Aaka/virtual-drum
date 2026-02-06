#include <esp_now.h>
#include <WiFi.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>

// --- REPLACE WITH YOUR NODEMCU MAC ADDRESS ---
// Check the Serial Monitor of the NodeMCU to get this!
uint8_t receiverAddress[] = {0x48, 0x3F, 0xDA, 0x8B, 0x23, 0x0B}; 

// --- CONFIG ---
const int BUTTON_PIN = 13;
const int GND_PIN = 12; // Software Ground
int STICK_ID = 2;       // 1 = Right Hand

// --- VARIABLES ---
Adafruit_MPU6050 mpu;
esp_now_peer_info_t peerInfo;
float prev_ax, prev_ay, prev_az;
unsigned long lastTrigger = 0;
int currentMode = 0;
bool lastButtonState = HIGH;

// --- DATA STRUCTURE ---
typedef struct struct_message {
  int id;
  int intensity; 
  int mode;
} struct_message;

struct_message myData;

void setup() {
  Serial.begin(115200);

  // 1. PIN SETUP
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(GND_PIN, OUTPUT);
  digitalWrite(GND_PIN, LOW); // "Duh" Ground

  // 2. WIFI SETUP (FORCE CHANNEL 1)
  WiFi.mode(WIFI_STA);
  WiFi.setChannel(1); // Crucial sync fix
  
  // 3. MPU6050 SETUP
  Wire.begin(21, 22); 
  if (!mpu.begin()) {
    Serial.println("MPU Fail!");
    while (1) yield();
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_16_G);

  // 4. ESP-NOW SETUP
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW Fail");
    return;
  }

  // 5. REGISTER PEER
  memcpy(peerInfo.peer_addr, receiverAddress, 6);
  peerInfo.channel = 1; // Force peer to Channel 1
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Pairing Fail");
    return;
  }
}

void loop() {
  // --- A. BUTTON LATCHING ---
  bool currentButtonState = digitalRead(BUTTON_PIN);
  if (lastButtonState == HIGH && currentButtonState == LOW) {
    currentMode = (currentMode == 0) ? 1 : 0; // Toggle
    delay(200); // Debounce
  }
  lastButtonState = currentButtonState;

  // --- B. MOTION DETECTION ---
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  float jerk = sqrt(pow(a.acceleration.x - prev_ax, 2) + 
                    pow(a.acceleration.y - prev_ay, 2) + 
                    pow(a.acceleration.z - prev_az, 2));

  if (jerk > 25.0 && (millis() - lastTrigger > 110)) {
    myData.id = STICK_ID;
    myData.intensity = constrain(map((long)jerk, 25, 100, 50, 255), 50, 255);
    myData.mode = currentMode;
    
    esp_now_send(receiverAddress, (uint8_t *) &myData, sizeof(myData));
    lastTrigger = millis();
  }

  prev_ax = a.acceleration.x;
  prev_ay = a.acceleration.y;
  prev_az = a.acceleration.z;
  delay(10); 
}
