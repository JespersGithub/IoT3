import time
import network
from machine import Pin, ADC
from umqtt.simple import MQTTClient
import json
import machine
import ntptime
import ussl  # Import the ssl module to enable TLS/SSL

# Wi-Fi credentials
SSID = "JESPERSPC"
PASSWORD = "Password1234"

# MQTT Broker details
MQTT_SERVER = "72.145.2.196"
MQTT_PORT = 8883  # Using secure TLS port
MQTT_CLIENT_ID = "ESP32_Client"
MQTT_TOPIC_DISTANCE = "esp32/ultrasound_data"
MQTT_TOPIC_EMPTY_BOX = "esp32/empty_box_status"
MQTT_TOPIC_LDR = "sensor/ldr"
MQTT_TOPIC_BATTERY = "battery/percentage"

# Define device owner (patient name or device owner)
DEVICE_OWNER = "Anna"  # Change this variable to the desired device owner

# HC-SR04 GPIO Pins (Ultrasound Sensor)
TRIG_PIN = 5
ECHO_PIN = 17
trigger = machine.Pin(TRIG_PIN, machine.Pin.OUT)
echo = machine.Pin(ECHO_PIN, machine.Pin.IN)

# LDR Sensor Pin (Light Dependent Resistor)
LDR_PIN = 35
THRESHOLD = 1000
ldr = ADC(Pin(LDR_PIN))
ldr.atten(ADC.ATTN_11DB)

# Battery ADC Pin
BATTERY_ADC_PIN = 34
adc = ADC(Pin(BATTERY_ADC_PIN))
adc.atten(ADC.ATTN_11DB)
adc.width(ADC.WIDTH_12BIT)

# LED GPIO Pins
GREEN_LED_PIN = 14
RED_LED_PIN = 15
green_led = Pin(GREEN_LED_PIN, Pin.OUT)
red_led = Pin(RED_LED_PIN, Pin.OUT)

# Initialize LEDs to off
green_led.value(0)
red_led.value(0)

# Battery characteristics
MAX_VOLTAGE = 4.2
MIN_VOLTAGE = 3.0
VOLTAGE_DIVIDER_RATIO = 2

# State tracking for sensors
previous_state = False  # To track LDR state (light/dark)
empty_box_published = False

# Time zone offset (e.g., UTC +1 for CET)
TIMEZONE_OFFSET = 1 * 3600  # Adjust to your timezone offset in seconds (1 hour = 3600 seconds)

# Function to connect to WiFi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    while not wlan.isconnected():
        print("Connecting to WiFi...")
        time.sleep(1)
    print("Connected to WiFi")
    print("IP address:", wlan.ifconfig()[0])

# Function to connect to MQTT using TLS/SSL
def connect_mqtt():
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_SERVER, port=MQTT_PORT, ssl=True)  # ssl=True to enable TLS
    try:
        print("Connecting to MQTT broker over TLS...")
        client.connect()
        print("Connected to MQTT broker")
        return client
    except Exception as e:
        print("Failed to connect to MQTT broker:", e)
        return None

# Function to sync time using NTP
def sync_time():
    try:
        print("Syncing time with NTP server...")
        ntptime.settime()  # Sync with default NTP server (pool.ntp.org)
        print("Time synced successfully.")
    except Exception as e:
        print(f"Error syncing time: {e}")

# Function to get the current time adjusted for the timezone
def get_current_time():
    # Get the current time from the ESP32
    t = time.localtime(time.time() + TIMEZONE_OFFSET)
    # Format as a readable string: [Year, Month, Day, Hour, Minute, Second, Weekday, Yearday]
    return "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(t[0], t[1], t[2], t[3], t[4], t[5])

# Ultrasound Sensor: Measure Distance
def measure_distance():
    try:
        trigger.value(0)
        time.sleep_us(2)
        trigger.value(1)
        time.sleep_us(10)
        trigger.value(0)

        pulse_duration = machine.time_pulse_us(echo, 1, 30000)
        if pulse_duration > 0:
            distance = (pulse_duration * 0.0343) / 2  # Convert to cm
            return distance
        else:
            print("Warning: No echo received or measurement timed out.")
            return None
    except Exception as e:
        print(f"Error measuring distance: {e}")
        return None

# Function to calculate battery percentage
def calculate_battery_percentage(voltage):
    if voltage >= MAX_VOLTAGE:
        return 100
    elif voltage <= MIN_VOLTAGE:
        return 0
    else:
        return int(((voltage - MIN_VOLTAGE) / (MAX_VOLTAGE - MIN_VOLTAGE)) * 100)

# Function to read battery voltage
def read_battery_voltage():
    raw_value = adc.read()
    voltage = (raw_value / 4095) * 3.3
    return voltage * VOLTAGE_DIVIDER_RATIO

# Function to publish data
def publish_data(client, topic, data):
    try:
        # Add device_owner (patient name) to the data
        data["device_owner"] = DEVICE_OWNER  # Include DEVICE_OWNER in the payload
        data["timestamp"] = get_current_time()  # Add current time to the payload
        message = json.dumps(data)
        client.publish(topic, message)
        print(f"Published data to {topic}: {message}")
    except Exception as e:
        print(f"Failed to publish data: {e}")

# Function to handle green LED based on LDR
def handle_green_led(ldr_value):
    if ldr_value > THRESHOLD:
        green_led.value(1)  # Turn on green LED
    else:
        green_led.value(0)  # Turn off green LED

# Function to handle red LED based on distance
def handle_red_led(distance):
    if distance > 2.9:  # Empty box condition
        red_led.value(1)  # Turn on red LED
    else:
        red_led.value(0)  # Turn off red LED

# Function to monitor LDR sensor
def monitor_ldr(client):
    global previous_state
    ldr_value = ldr.read()
    print(f"LDR Value: {ldr_value}")

    # Control green LED
    handle_green_led(ldr_value)

    if ldr_value > THRESHOLD and not previous_state:
        print("Light detected! Sending data...")
        ldr_data = {"value": 1}
        publish_data(client, MQTT_TOPIC_LDR, ldr_data)
        previous_state = True
    elif ldr_value <= THRESHOLD and previous_state:
        print("Darkness detected. Ready for next light detection.")
        previous_state = False
    time.sleep(0.5)

# Main function
def main():
    connect_wifi()
    mqtt_client = connect_mqtt()

    if mqtt_client:
        sync_time()  # Sync time with NTP
        last_regular_publish = time.time()
        global empty_box_published
        try:
            while True:
                # Ultrasound sensor: measure distance
                distance = measure_distance()
                if distance is not None:
                    print(f"Measured Distance: {distance:.2f} cm")

                    # Control red LED
                    handle_red_led(distance)

                    # Publish regular distance data every 10 seconds
                    if time.time() - last_regular_publish >= 10:
                        sensor_data = {"distance": distance}
                        publish_data(mqtt_client, MQTT_TOPIC_DISTANCE, sensor_data)
                        last_regular_publish = time.time()

                    # Publish box status
                    if distance > 2.9 and not empty_box_published:
                        empty_box_data = {"status": "empty", "distance": distance}
                        publish_data(mqtt_client, MQTT_TOPIC_EMPTY_BOX, empty_box_data)
                        empty_box_published = True
                        print("Empty box state detected and published.")

                    elif distance <= 2.9 and empty_box_published:
                        empty_box_data = {"status": "full", "distance": distance}
                        publish_data(mqtt_client, MQTT_TOPIC_EMPTY_BOX, empty_box_data)
                        empty_box_published = False
                        print("Box is now full. Status updated.")

                # LDR sensor: Monitor and publish light detection
                monitor_ldr(mqtt_client)

                # Battery sensor: Read battery voltage and percentage
                voltage = read_battery_voltage()
                percentage = calculate_battery_percentage(voltage)
                print(f"Battery Voltage: {voltage:.2f} V, Battery Percentage: {percentage}%")
                battery_data = {"voltage": voltage, "percentage": percentage}
                publish_data(mqtt_client, MQTT_TOPIC_BATTERY, battery_data)

                # Sleep to avoid rapid sensor polling
                time.sleep(1)

        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            mqtt_client.disconnect()
            print("MQTT client disconnected.")
    else:
        print("MQTT connection failed. Exiting.")

if __name__ == "__main__":
    main()
