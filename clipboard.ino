#include "BLEDevice.h"
#include "BLEHIDDevice.h"
#include "HIDTypes.h"
#include "HIDKeyboardTypes.h"

BLEHIDDevice* hid;
BLECharacteristic* input;
bool connected = false;
String textToType = "";
bool isTyping = false;
unsigned long lastCharTime = 0;
int currentCharIndex = 0;
int charDelay = 0;

static const uint8_t hidReportDescriptor[] = {
  0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x85, 0x01, 0x05, 0x07,
  0x19, 0xE0, 0x29, 0xE7, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01,
  0x95, 0x08, 0x81, 0x02, 0x95, 0x01, 0x75, 0x08, 0x81, 0x01,
  0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x25, 0x65, 0x05, 0x07,
  0x19, 0x00, 0x29, 0x65, 0x81, 0x00, 0xC0
};

uint8_t getKeyCode(char c) {
  if (c >= 'a' && c <= 'z') return c - 'a' + 0x04;
  if (c >= 'A' && c <= 'Z') return c - 'A' + 0x04;
  if (c >= '1' && c <= '9') return c - '1' + 0x1E;
  if (c == '0') return 0x27;
  if (c == ' ') return 0x2C;
  if (c == '\n' || c == '\r') return 0x28;
  if (c == '\t') return 0x2B;
  if (c == '-') return 0x2D;
  if (c == '=') return 0x2E;
  if (c == '[') return 0x2F;
  if (c == ']') return 0x30;
  if (c == '\\') return 0x31;
  if (c == ';') return 0x33;
  if (c == '\'') return 0x34;
  if (c == '`') return 0x35;
  if (c == ',') return 0x36;
  if (c == '.') return 0x37;
  if (c == '/') return 0x38;
  if (c == '!') return 0x1E;
  if (c == '@') return 0x1F;
  if (c == '#') return 0x20;
  if (c == '$') return 0x21;
  if (c == '%') return 0x22;
  if (c == '^') return 0x23;
  if (c == '&') return 0x24;
  if (c == '*') return 0x25;
  if (c == '(') return 0x26;
  if (c == ')') return 0x27;
  if (c == '_') return 0x2D;
  if (c == '+') return 0x2E;
  if (c == '{') return 0x2F;
  if (c == '}') return 0x30;
  if (c == '|') return 0x31;
  if (c == ':') return 0x33;
  if (c == '"') return 0x34;
  if (c == '~') return 0x35;
  if (c == '<') return 0x36;
  if (c == '>') return 0x37;
  if (c == '?') return 0x38;
  return 0;
}

bool needsShift(char c) {
  if (c >= 'A' && c <= 'Z') return true;
  return (c == '!' || c == '@' || c == '#' || c == '$' || c == '%' || 
          c == '^' || c == '&' || c == '*' || c == '(' || c == ')' ||
          c == '_' || c == '+' || c == '{' || c == '}' || c == '|' ||
          c == ':' || c == '"' || c == '~' || c == '<' || c == '>' || 
          c == '?');
}

class MyCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) {
    connected = true;
    Serial.println("BLE Connected - Ready to type!");
  }
  void onDisconnect(BLEServer* pServer) {
    connected = false;
    isTyping = false;
    Serial.println("BLE Disconnected");
    BLEDevice::startAdvertising();
  }
};

// =======================================================
// =========== ROBUST KEYPRESS SENDING FUNCTION ==========
// =======================================================
void sendKeyPress(uint8_t modifier, uint8_t key) {
  if (!connected) return;
  // 1. Create the Key Press Report
  uint8_t report[8] = { modifier, 0x00, key, 0x00, 0x00, 0x00, 0x00, 0x00 };
  
  // 2. Send the Key Press
  input->setValue(report, sizeof(report));
  input->notify();

  // A small delay is crucial for some operating systems
  delay(10); 

  // 3. Create the Key Release Report (all keys and modifiers up)
  uint8_t releaseReport[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};

  // 4. Send the Key Release
  input->setValue(releaseReport, sizeof(releaseReport));
  input->notify();
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(100); // Set a short timeout for serial reading
  Serial.println("\n=== ESP32 Keyboard Controller ===");
  Serial.println("Protocol: TYPE:<length>:<text>");
  
  BLEDevice::init("Hirdy-Keyboard");
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyCallbacks());

  hid = new BLEHIDDevice(pServer);
  input = hid->inputReport(1);

  hid->manufacturer()->setValue("ESP32-Dev");
  hid->pnp(0x02, 0xe502, 0xa111, 0x0210);
  hid->hidInfo(0x00, 0x02);

  BLESecurity *pSecurity = new BLESecurity();
  pSecurity->setAuthenticationMode(ESP_LE_AUTH_BOND);

  hid->reportMap((uint8_t*)hidReportDescriptor, sizeof(hidReportDescriptor));
  hid->startServices();

  BLEAdvertising *pAdvertising = pServer->getAdvertising();
  pAdvertising->setAppearance(HID_KEYBOARD);
  pAdvertising->addServiceUUID(hid->hidService()->getUUID());
  pAdvertising->start();

  Serial.println("✓ BLE HID Keyboard ready!");
  Serial.println("✓ Waiting for connection...\n");
}

// =======================================================
// ============= NEW COMMAND PARSING LOGIC ===============
// =======================================================
void loop() {
  // Handle Serial commands
  if (Serial.available()) {
    // Read the command type (e.g., "TYPE", "STOP")
    String command = Serial.readStringUntil(':');
    command.toUpperCase();

    if (command == "TYPE") {
      // Read the expected length of the text
      String lenStr = Serial.readStringUntil(':');
      int length = lenStr.toInt();
      
      if (length > 0) {
        // Read the exact number of bytes for the text
        char textBuffer[length + 1];
        Serial.readBytes(textBuffer, length);
        textBuffer[length] = '\0'; // Null-terminate the string
        textToType = String(textBuffer);

        if (connected) {
            isTyping = true;
            currentCharIndex = 0;
            lastCharTime = millis();
            charDelay = random(80, 120);
            Serial.println("Starting to type text. Length: " + String(length));
        } else {
            Serial.println(" Error: BLE not connected! Please pair device first.");
        }
      } else {
        Serial.println(" Error: Invalid or zero length received.");
      }
    }
    else if (command == "STOP") {
      isTyping = false;
      Serial.println("  Typing stopped by command.");
    }
    else if (command == "STATUS") {
      Serial.println(" STATUS: Connected=" + String(connected) + ", Typing=" + String(isTyping));
    }
    else if (command == "CLEAR") {
      textToType = "";
      isTyping = false;
      currentCharIndex = 0;
      Serial.println(" Text buffer cleared.");
    }
  }
  
  // Handle typing process (this part remains the same)
  if (isTyping && connected && (millis() - lastCharTime >= charDelay)) {
    if (currentCharIndex < textToType.length()) {
      char c = textToType.charAt(currentCharIndex);
      uint8_t key = getKeyCode(c);
      
      if (key != 0) {
        uint8_t modifier = needsShift(c) ? 0x02 : 0x00; // 0x02 = Left Shift
        sendKeyPress(modifier, key);
      } else {
        Serial.println("⚠️  Skipped unsupported character: " + String(c));
      }
      currentCharIndex++;
      lastCharTime = millis();
      charDelay = random(90, 150);
    } else {
      isTyping = false;
      Serial.println(" Finished typing all text!");
    }
  }
}