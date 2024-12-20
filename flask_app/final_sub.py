import mysql.connector
from datetime import datetime
import json
import pytz
import paho.mqtt.client as mqtt
import ssl

# Database connection setup
def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="azureuser",  # Your MySQL username
        password="Password1234",  # Your MySQL password
        database="sensor_data"  # Your MySQL database name
    )

# Callback function for incoming MQTT messages
def on_message(client, userdata, message):
    try:
        # Decode the received MQTT message
        received_data = message.payload.decode()

        # Set the time zone to Denmark (Copenhagen)
        denmark_tz = pytz.timezone("Europe/Copenhagen")
        timestamp = datetime.now(denmark_tz)  # Use datetime object with Denmark's timezone

        if message.topic == "sensor/ldr":
            print(f"Received message on {message.topic}: {received_data}")
            data = json.loads(received_data)
            print(f"Parsed data: {data}")

            if data.get("value") == 1:  # Check if value is 1
                print(f"Light detected at {timestamp}")
                create_table("ldr_data", """
                    CREATE TABLE IF NOT EXISTS ldr_data (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        timestamp DATETIME NOT NULL,
                        value INT NOT NULL,
                        device_owner VARCHAR(255) NOT NULL
                    );
                """)
                # Insert data including device owner
                insert_data("ldr_data", (timestamp, data.get("value"), get_device_owner(data)))
            else:
                print("LDR value is not 1, skipping insertion.")

        elif message.topic == "esp32/ultrasound_data":
            print(f"Received message on {message.topic}: {received_data}")
            data = json.loads(received_data)

            if "distance" in data:
                distance = data["distance"]
                print(f"Parsed Distance: {distance}, Timestamp: {timestamp}")
                create_table("ultrasound_data", """
                    CREATE TABLE IF NOT EXISTS ultrasound_data (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        timestamp DATETIME NOT NULL,
                        value FLOAT NOT NULL,
                        device_owner VARCHAR(255) NOT NULL
                    );
                """)
                # Insert data including device owner
                insert_data("ultrasound_data", (timestamp, distance, get_device_owner(data)))

        elif message.topic == "esp32/empty_box_status":
            print(f"Received message on {message.topic}: {received_data}")
            data = json.loads(received_data)

            if "status" in data:
                status = data["status"]
                distance = data.get("distance", None)
                print(f"Parsed Empty Box Status: {status}, Distance: {distance}, Timestamp: {timestamp}")
                create_table("empty_box_status", """
                    CREATE TABLE IF NOT EXISTS empty_box_status (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        timestamp DATETIME NOT NULL,
                        status VARCHAR(10) NOT NULL,
                        distance FLOAT,
                        device_owner VARCHAR(255) NOT NULL
                    );
                """)
                # Insert data including device owner
                insert_data("empty_box_status", (timestamp, status, distance, get_device_owner(data)))

        elif message.topic == "battery/percentage":
            print(f"Received message on {message.topic}: {received_data}")

            # Extract the voltage and percentage from the message
            data = json.loads(received_data)
            voltage = float(data.get("voltage", 0.0))  # Convert voltage to float
            percentage = int(data.get("percentage", 0))  # Convert percentage to int

            print(f"Received data: Voltage = {voltage} V, Percentage = {percentage}% at {timestamp}")
            create_table("battery_data", """
                CREATE TABLE IF NOT EXISTS battery_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    voltage FLOAT NOT NULL,
                    percentage INT NOT NULL,
                    device_owner VARCHAR(255) NOT NULL
                );
            """)
            # Insert data including device owner
            insert_data("battery_data", (timestamp, voltage, percentage, get_device_owner(data)))

        else:
            print("Unrecognized message format or topic.")

    except Exception as e:
        print(f"Error processing message: {e}")

# Function to extract device_owner from the message data
def get_device_owner(data):
    # Check if the data has a 'device_owner' field and return it
    if isinstance(data, dict) and "device_owner" in data:
        return data["device_owner"]
    else:
        return "Unknown"  # Default value if no owner is found

# Ensure the table exists
def create_table(table_name, create_query):
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute(create_query)
        conn.commit()
        conn.close()
        print(f"Table '{table_name}' checked/created.")
    except mysql.connector.Error as err:
        print(f"MySQL error while creating table '{table_name}': {err}")

# Insert data into a table
def insert_data(table_name, values):
    try:
        conn = connect_db()
        cur = conn.cursor()

        if table_name == "ldr_data":
            query = "INSERT INTO ldr_data (timestamp, value, device_owner) VALUES (%s, %s, %s);"
        elif table_name == "ultrasound_data":
            query = "INSERT INTO ultrasound_data (timestamp, value, device_owner) VALUES (%s, %s, %s);"
        elif table_name == "empty_box_status":
            query = "INSERT INTO empty_box_status (timestamp, status, distance, device_owner) VALUES (%s, %s, %s, %s);"
        elif table_name == "battery_data":
            query = "INSERT INTO battery_data (timestamp, voltage, percentage, device_owner) VALUES (%s, %s, %s, %s);"

        cur.execute(query, values)
        conn.commit()
        print(f"Data inserted into '{table_name}': {values}")
    except mysql.connector.Error as err:
        print(f"MySQL error while inserting data into '{table_name}': {err}")
    finally:
        conn.close()

# MQTT Client Setup
def connect_mqtt():
    client = mqtt.Client()

    # Set up TLS connection
    client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLSv1_2)
    client.tls_insecure_set(True)  # Disable certificate verification for testing
    client.username_pw_set(username="YOUR_USERNAME", password="YOUR_PASSWORD")  # Add credentials if needed

    # Assign callback function
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print("Connecting to MQTT broker...")
        client.connect("72.145.2.196", 8883, 60)
        print("Connected successfully.")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return None

    return client

# Function to handle subscription and messages
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code: {rc}")
    # Subscribe to topics after connection
    client.subscribe([("sensor/ldr", 0), ("esp32/ultrasound_data", 0), ("esp32/empty_box_status", 0), ("battery/percentage", 0)])

# Main function to run the subscriber
def main():
    client = connect_mqtt()
    if client:
        # Start listening for messages
        print("Waiting for messages...")
        client.loop_forever()  # Block and listen for messages

if __name__ == "__main__":
    main()
