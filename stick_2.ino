#include <ESP8266WiFi.h>
#include <espnow.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>

// 1. RECEIVER MAC ADDRESS (Replace with the receiver's MAC)
uint8_t receiverAddress[] = {0x20, 0xE7, 0xC8, 0xBA, 0x68, 0xA0};

// 2. STICK CONFIG
int STICK_ID = 2; 

Adafruit_MPU6050 mpu;
float prev_ax, prev_ay, prev_az;
unsigned long lastTrigger = 0;

// Data Packet Structure (Must match receiver exactly)
typedef struct struct_message {
  int id;
  int intensity; 
} struct_message;

struct_message myData;

// Callback when data is sent (Optional debugging)
void onDataSent(uint8_t *mac_addr, uint8_t sendStatus) {
  // Serial.print("Send Status: ");
  // Serial.println(sendStatus == 0 ? "Success" : "Fail");
}

void setup() {
  Serial.begin(115200);
  
  // Set WiFi to Station mode
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(); // Ensure we aren't trying to connect to a router

  // MPU6050 Init
  // Note: On ESP8266, default I2C is usually D2 (SDA) and D1 (SCL)
  if (!mpu.begin()) {
    Serial.println("MPU6050 not found!");
    while (1) delay(10);
  }

  // Init ESP-NOW for ESP8266
  if (esp_now_init() != 0) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // ESP8266 Role: Controller (Transmitter)
  esp_now_set_self_role(ESP_NOW_ROLE_CONTROLLER);
  esp_now_register_send_cb(onDataSent);
  
  // Add Peer
  esp_now_add_peer(receiverAddress, ESP_NOW_ROLE_SLAVE, 1, NULL, 0);
  
  // Setup Sensor Ranges
  mpu.setAccelerometerRange(MPU6050_RANGE_16_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
}

void loop() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  // Calculate Jerk magnitude
  float jerk = sqrt(pow(a.acceleration.x - prev_ax, 2) + 
                    pow(a.acceleration.y - prev_ay, 2) + 
                    pow(a.acceleration.z - prev_az, 2));

  float min_jerk = 15.0; 
  float max_jerk = 80.0; 

  if (jerk > min_jerk && (millis() - lastTrigger > 120)) {
    myData.id = STICK_ID;
    
    int velocity = map((long)jerk, (long)min_jerk, (long)max_jerk, 50, 255);
    myData.intensity = constrain(velocity, 50, 255);
    
    // ESP8266 specific send function
    esp_now_send(receiverAddress, (uint8_t *) &myData, sizeof(myData));
    
    lastTrigger = millis();
  }

  prev_ax = a.acceleration.x;
  prev_ay = a.acceleration.y;
  prev_az = a.acceleration.z;
  delay(5); 
}