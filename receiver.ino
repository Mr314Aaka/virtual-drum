#include <esp_now.h>
#include <WiFi.h>

// Data structure must match the sender
typedef struct struct_message {
  int id;
  int intensity;
} struct_message;

struct_message myData;

// Volatile flag to safely trigger the main loop
volatile bool newData = false;

// --- THE FIX IS HERE ---
// Old version: void onDataRecv(const uint8_t * mac, ...
// New version: void onDataRecv(const esp_now_recv_info_t * info, ...
void onDataRecv(const esp_now_recv_info_t * info, const uint8_t *incomingData, int len) {
  // Verify data length to prevent corruption
  if (len == sizeof(myData)) {
    memcpy(&myData, incomingData, sizeof(myData));
    newData = true; // Signal the loop to print
  }
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  
  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    delay(3000);
    ESP.restart();
  }
  
  // Register the callback (Now compatible with v3.0)
  esp_now_register_recv_cb(onDataRecv);
  
  Serial.println("Receiver Ready. Waiting for sticks...");
}

void loop() {
  // We print inside the loop to avoid crashing the callback
  if (newData) {
    Serial.print(myData.id);
    Serial.print(":");
    Serial.println(myData.intensity);
    newData = false; 
  }
}