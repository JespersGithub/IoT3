from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import base64
from datetime import datetime, timedelta
import pytz
import logging
from flask_mail import Mail, Message

# Initialize Flask app
app = Flask(__name__)

# Secret key for session management
app.secret_key = 'your_secret_key'  # Replace with a real secret key for session security

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Replace with your SMTP server
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'srbin@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'Srbin12345678'  # Replace with your email password

mail = Mail(app)

@app.route('/send_mail', methods=['POST'])
def send_mail():
    """Handle sending an email."""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        msg = Message("Hello from your Website",
                      sender="@gmail.com",  # Replace with your email
                      recipients=["recipient_email@gmail.com"])  # Replace with recipient's email
        msg.body = "This is a test email sent from your Flask website!"
        mail.send(msg)
        return "Mail sent successfully!", 200
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return f"Failed to send email: {e}", 500

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

def connect_db():
    """Connect to the database."""
    return mysql.connector.connect(
        host="localhost",
        user="xxx",
        password="xxx",
        database="sensor_data"
    )

def generate_plot(data):
    """Generate ultrasound plot."""
    fig, ax = plt.subplots(figsize=(8, 4))  # Adjusted size (width, height)

    # Assuming the second column is the timestamp and the third is the value
    timestamps = [row[1] for row in data]  # Extract timestamps from the database
    values = [float(row[2]) for row in data]  # Extract values from the database

    # Get the timezone for Denmark (Copenhagen)
    denmark_timezone = pytz.timezone('Europe/Copenhagen')

    # Convert the timestamps to Denmark timezone
    timestamps = [timestamp.replace(tzinfo=pytz.utc).astimezone(denmark_timezone) if timestamp.tzinfo is None else timestamp.astimezone(denmark_timezone) for timestamp in timestamps]

    # Define the start and end time for the 24-hour period
    today_start = datetime.now(denmark_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # Plot the data
    ax.plot(timestamps, values, marker='o', linestyle='-', color='b')
    ax.set_title('Ultrasound Sensor Data')
    ax.set_xlabel('Time of Day')
    ax.set_ylabel('Distance (cm)')

    # Set proper date format for the x-axis to show only the time portion (HH:MM)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))  # HH:MM format

    # Set the x-axis limits to cover the entire 24-hour period
    ax.set_xlim(today_start, today_end)

    # Set the x-axis major locator to have ticks every 2 hours
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))  # Ticks every 2 hours

    # Rotate date labels for better readability
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save the plot to a BytesIO object
    img = BytesIO()
    fig.savefig(img, format='png')
    img.seek(0)
    return img

# Function to generate LDR-specific plot
def generate_ldr_plot(data):
    """Generate LDR plot."""
    fig, ax = plt.subplots(figsize=(8, 4))  # Adjusted size (width, height)

    # Get the timezone for Denmark (Copenhagen)
    denmark_timezone = pytz.timezone('Europe/Copenhagen')

    # Define the start and end time for the 24-hour period
    today_start = datetime.now(denmark_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # Filter data for "1" values and convert timestamps to Denmark timezone
    ldr_timestamps = [row[1] for row in data if float(row[2]) == 1]
    ldr_timestamps = [timestamp.replace(tzinfo=pytz.utc).astimezone(denmark_timezone) if timestamp.tzinfo is None else timestamp.astimezone(denmark_timezone) for timestamp in ldr_timestamps]

    # Plot dots at the times when the LDR is triggered
    ax.plot(ldr_timestamps, [1]*len(ldr_timestamps), 'bo', label="LDR Openings")

    # Set the x-axis to cover the entire 24-hour period
    ax.set_xlim(today_start, today_end)
    ax.set_ylim(0, 1.2)  # Space above the graph for better visualization
    ax.set_title('LDR Data - Open Times')
    ax.set_xlabel('Time of Day')
    ax.set_ylabel('Detection')

    # Set proper date format for the x-axis to show only the time portion (HH:MM)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))  # HH:MM format

    # Set the x-axis major locator to have ticks every 1 hour
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))  # Ticks every 1 hour

    # Rotate date labels for better readability
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save the plot to a BytesIO object
    img = BytesIO()
    fig.savefig(img, format='png')
    img.seek(0)
    return img

# Route for login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:  # Check if the user is already logged in
        return redirect(url_for('home'))  # Redirect to home if already logged in

    error_message = None  # Initialize the error message variable

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Dummy login validation (replace with your real logic)
        if username == 'xxx' and password == 'xxx':
            session['username'] = username  # Store the username in session
            return redirect(url_for('home'))  # Redirect to home page after successful login
        else:
            error_message = "Invalid credentials. Please try again."  # Set error message for wrong credentials

    return render_template('login.html', error_message=error_message)  # Pass error message to template

# Logout route to clear the session
@app.route('/logout')
def logout():
    session.pop('username', None)  # Remove the username from the session
    return redirect(url_for('login'))  # Redirect to the login page

@app.route('/info')
def info():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('info.html')

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        logging.debug("Connecting to database...")
        conn = connect_db()
        cursor = conn.cursor()

        # Fetch ultrasound data for the last 24 hours
        cursor.execute("SELECT * FROM ultrasound_data WHERE timestamp > NOW() - INTERVAL 1 DAY ORDER BY timestamp DESC;")
        ultrasound_data = cursor.fetchall()

        # Fetch LDR data for today
        cursor.execute("SELECT * FROM ldr_data WHERE DATE(timestamp) = CURDATE();")
        ldr_data = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM ldr_data WHERE DATE(timestamp) = CURDATE() AND value = 1;")
        ldr_open_count_result = cursor.fetchone()
        ldr_open_count = ldr_open_count_result[0] if ldr_open_count_result and ldr_open_count_result[0] is not None else 0

        # Fetch the box status (empty/full) and limit to 10 latest records
        cursor.execute("SELECT * FROM empty_box_status ORDER BY timestamp DESC LIMIT 10;")
        empty_box_data = cursor.fetchall()
        logging.debug(f"Fetched empty_box_data: {empty_box_data}")  # Add debug log for box status data

        # Fetch the most recent battery data
        cursor.execute("SELECT * FROM battery_data ORDER BY timestamp DESC LIMIT 1;")
        battery_data = cursor.fetchall()

        conn.close()

        # Generate the plots with the fetched data
        ultrasound_plot = generate_plot(ultrasound_data)
        ldr_plot = generate_ldr_plot(ldr_data)

        # Convert the plots to base64 for embedding in HTML
        ultrasound_plot_b64 = base64.b64encode(ultrasound_plot.getvalue()).decode('utf-8')
        ldr_plot_b64 = base64.b64encode(ldr_plot.getvalue()).decode('utf-8')

        # Pass the base64-encoded plots and data to the template
        return render_template('index.html', 
                               ultrasound_plot=ultrasound_plot_b64, 
                               ldr_plot=ldr_plot_b64, 
                               ldr_open_count=ldr_open_count,
                               empty_box_data=empty_box_data,
                               battery_data=battery_data)  # Pass battery data here

    except mysql.connector.Error as err:
        logging.error(f"Database Error: {err}")
        return f"Error: {err}"

    except Exception as e:
        logging.error(f"Error: {e}")
        return f"Error: {e}"


@app.route('/patient/<patient_name>')
def patient_data(patient_name):
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        # Connect to the database
        conn = connect_db()
        cursor = conn.cursor()

        # Fetch ultrasound data for the last 24 hours for the specific patient
        cursor.execute("""SELECT * FROM ultrasound_data WHERE device_owner = %s AND timestamp > NOW() - INTERVAL 1 DAY ORDER BY timestamp DESC;""", (patient_name,))
        ultrasound_data = cursor.fetchall()

        # Fetch LDR data for today for the specific patient
        cursor.execute("""SELECT * FROM ldr_data WHERE device_owner = %s AND DATE(timestamp) = CURDATE();""", (patient_name,))
        ldr_data = cursor.fetchall()

        # Fetch the count of LDR openings (value = 1) for today
        cursor.execute("""SELECT COUNT(*) FROM ldr_data WHERE device_owner = %s AND DATE(timestamp) = CURDATE() AND value = 1;""", (patient_name,))
        ldr_open_count_result = cursor.fetchone()
        ldr_open_count = ldr_open_count_result[0] if ldr_open_count_result and ldr_open_count_result[0] is not None else 0

        # Fetch all battery data for the specific patient
        cursor.execute("""SELECT * FROM battery_data WHERE device_owner = %s ORDER BY timestamp DESC LIMIT 10;""", (patient_name,))
        battery_data = cursor.fetchall()  # Fetch multiple records

        # Fetch box status (empty/full) for the specific patient
        cursor.execute("""SELECT * FROM empty_box_status WHERE device_owner = %s ORDER BY timestamp DESC LIMIT 10;""", (patient_name,))
        empty_box_status = cursor.fetchall()  # This will fetch all records

        conn.close()

        # Generate the plots with the fetched data
        ultrasound_plot = generate_plot(ultrasound_data)
        ldr_plot = generate_ldr_plot(ldr_data)

        # Convert the plots to base64 for embedding in HTML
        ultrasound_plot_b64 = base64.b64encode(ultrasound_plot.getvalue()).decode('utf-8')
        ldr_plot_b64 = base64.b64encode(ldr_plot.getvalue()).decode('utf-8')

        # Pass the data to the template
        return render_template('patient_data.html', 
                               patient_name=patient_name,
                               ultrasound_plot=ultrasound_plot_b64, 
                               ldr_plot=ldr_plot_b64, 
                               ldr_open_count=ldr_open_count,
                               battery_data=battery_data,  # Pass the battery data as a list of records
                               empty_box_status=empty_box_status)  # Corrected name

    except mysql.connector.Error as err:
        logging.error(f"Database Error: {err}")
        return f"Error: {err}"

    except Exception as e:
        logging.error(f"Error: {e}")
        return f"Error: {e}"


if __name__ == "__main__":
     app.run(debug=True)
