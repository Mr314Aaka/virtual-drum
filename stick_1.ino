#include <WiFi.h>

void setup() {
  // 1. Lower the baud rate to 115200 for better stability
  Serial.begin(115200); 
  while (!Serial); 
  delay(1000);

  // 2. Explicitly set to Station Mode
  WiFi.mode(WIFI_STA);
  
  // 3. Give the hardware a tiny bit of time to initialize
  delay(100); 

  Serial.println("\n--- Hardware Check ---");
  
  // 4. Retrieve the MAC
  String mac = WiFi.macAddress();
  
  if (mac == "00:00:00:00:00:00") {
    Serial.println("Error: WiFi hardware not ready. Restarting...");
    ESP.restart(); // Software reset if it fails
  } else {
    Serial.print("Board MAC Address: ");
    Serial.println(mac);
  }
}

void loop() {}