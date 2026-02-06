#include <ESP8266WiFi.h>
#include <espnow.h>

// --- DATA STRUCTURE (Must Match Sender) ---
typedef struct struct_message {
    int id;
    int intensity;
    int mode;
} struct_message;

struct_message myData;

// --- CALLBACK ---
void onDataRecv(uint8_t * mac, uint8_t *incomingData, uint8_t len) {
  memcpy(&myData, incomingData, sizeof(myData));
  
  // PRINT FORMAT:  ID:INTENSITY:MODE
  Serial.print(myData.id);
  Serial.print(":");
  Serial.print(myData.intensity);
  Serial.print(":");
  Serial.println(myData.mode);
}

void setup() {
  Serial.begin(115200);
  
  // 1. WIFI SETUP
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  
  // 2. FORCE CHANNEL 1 (The Magic Fix)
  wifi_set_channel(1); 

  // 3. INIT ESP-NOW
  if (esp_now_init() != 0) {
    Serial.println("Init Failed");
    return;
  }

  esp_now_set_self_role(ESP_NOW_ROLE_SLAVE);
  esp_now_register_recv_cb(onDataRecv);

  // 4. PRINT MAC (COPY THIS!)
  Serial.println("--- READY ---");
  Serial.print("MAC ADDR: {");
  
  uint8_t mac[6];
  WiFi.macAddress(mac);
  for (int i = 0; i < 6; i++) {
    Serial.print("0x");
    Serial.print(mac[i], HEX);
    if (i < 5) Serial.print(", ");
  }
  Serial.println("};");
  Serial.println("COPY THE LINE ABOVE INTO YOUR ESP32 CODE");
}

void loop() {
  yield(); // Keep watchdog happy
}
