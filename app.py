import os
import threading
import sqlite3
import time
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from inference_sdk import InferenceHTTPClient, InferenceConfiguration
import paho.mqtt.client as mqtt_client
from translate import Translator
import random
import logging
import shutil

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Replace with your secret key
translator = Translator(to_lang="id")  # Set up translator to Indonesian

# Set up a directory to store uploaded files
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize the InferenceHTTPClient
CLIENT = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key="nXHlQP10OlbsjZEzF2Re"
)
# Define custom configuration with confidence threshold
custom_configuration = InferenceConfiguration(confidence_threshold=0.3)

# Global variable to store the weight data
weight_data = None

# MQTT settings
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "trash/weight"

client_id = f'python-mqtt-{random.randint(0, 1000)}'
mqtt_client = mqtt_client.Client(client_id=client_id, clean_session=True, userdata=None, protocol=mqtt_client.MQTTv311)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker with result code {rc}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Failed to connect to MQTT broker. Return code: {rc}")

def on_message(client, userdata, msg):
    global weight_data
    weight_data = float(msg.payload.decode())
    print(f"New weight data received: {weight_data}")  # Debugging: print the latest incoming data

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60

def on_disconnect(client, userdata, rc):
    logging.info("Disconnected with result code: %s", rc)
    reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
    while reconnect_count < MAX_RECONNECT_COUNT:
        logging.info("Reconnecting in %d seconds...", reconnect_delay)
        time.sleep(reconnect_delay)

        try:
            client.reconnect()
            logging.info("Reconnected successfully!")
            return
        except Exception as err:
            logging.error("%s. Reconnect failed. Retrying...", err)

        reconnect_delay *= RECONNECT_RATE
        reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
        reconnect_count += 1
    logging.info("Reconnect failed after %s attempts. Exiting...", reconnect_count)

mqtt_client.on_disconnect = on_disconnect

# Start MQTT client in a separate thread with reconnection logic
def mqtt_thread():
    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
            mqtt_client.loop_forever()
        except Exception as e:
            print(f"MQTT connection error: {e}")
            time.sleep(1)  # Wait before retrying

threading.Thread(target=mqtt_thread).start()

# Create a database and a users table
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS history
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       username TEXT NOT NULL,
                       image_path TEXT NOT NULL,
                       weight REAL NOT NULL,
                       trash_type TEXT NOT NULL,
                       timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def save_history(username, file_path, weight_data, trash_info):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    for trash in trash_info:
        cursor.execute('''INSERT INTO history (username, image_path, weight, trash_type)
                          VALUES (?, ?, ?, ?)''', (username, file_path, weight_data, trash['trash_type']))
    conn.commit()
    conn.close()

# Function to validate login credentials
def validate_login(username, password):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    if user and check_password_hash(user[2], password):
        return True
    return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if validate_login(username, password):
            session['username'] = username  # Store username in session
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
def index():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    global weight_data
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', error="No file part", user=username)

        file = request.files['file']

        if file.filename == '':
            return render_template('index.html', error="No selected file", user=username)

        # Save the uploaded file to the uploads folder
        global file_path
        filename = f"{time.strftime('%Y-%m-%d%H.%M.%S')}{random.randint(100000, 999999)}.jpg"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        relative_file_path = os.path.relpath(file_path, app.root_path)

        with open(file_path, 'rb') as f:
            image_data = f.read()

        with CLIENT.use_configuration(custom_configuration):
            result = CLIENT.infer(file_path, model_id="trash-detection-otdmj/35")

        if 'predictions' in result:
            global trash_info
            predictions = result['predictions']
            num_trash_detected = len(predictions)
            # if num_trash_detected > 0:
            if True:
                trash_info = []
                for prediction in predictions:
                    trash_type = prediction['class']
                    confidence = prediction['confidence']
                    x_coord = prediction['x']
                    y_coord = prediction['y']
                    # translated_trash_type = translator.translate(trash_type)
                    translated_trash_type = "Botol Plastik"
                    # trash_info.append({"trash_type": translated_trash_type})
                    trash_info.append({"trash_type": "Botol Plastik"})

                    # Save to history
                    conn = sqlite3.connect('users.db')
                    cursor = conn.cursor()
                    cursor.execute('''INSERT INTO history (username, image_path, weight, trash_type)
                                      VALUES (?, ?, ?, ?)''', (username, relative_file_path, weight_data, translated_trash_type))
                    conn.commit()
                    conn.close()

                # Render the page with trash info and prompt for weighing
                return render_template('index.html', trash_info=trash_info, prompt_weighing=True, user=username)
            else:
                return render_template('index.html', message="No trash detected in the image.", user=username)
        else:
            return render_template('index.html', message="No predictions found in the result.", user=username)

    # Check if weight data has been received
    if weight_data is not None:
        weight = weight_data
        weight_data = None  # Reset the weight data
        return render_template('index.html', weight=weight, user=username)

    return render_template('index.html', user=username)


@app.route('/history')
def history():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT username, image_path, weight, trash_type FROM history WHERE username = ?''', (username,))
    history_entries = cursor.fetchall()
    conn.close()
    
    return render_template('history.html', history_entries=history_entries, user=username)

@app.route('/get_weight', methods=['GET'])
def get_weight():
    global weight_data
    if weight_data is not None:
        weight = weight_data
        return jsonify({'weight': weight})
    return jsonify({'weight': None})

@app.route('/save_history', methods=['POST'])
def save_history_route():
    global weight_data, trash_info, file_path

    username = session.get('username')
    if not username:
        return jsonify({'error': 'User not logged in'})

    if weight_data is None:
        return jsonify({'error': 'No weight data or trash info available'})

    # Copy the file to /static/uploads directory
    destination_path = os.path.join(app.static_folder, 'uploads', os.path.basename(file_path))
    shutil.copyfile(file_path, destination_path)

    # Save history with the copied file path
    save_history(username, destination_path, weight_data, trash_info)
    time.sleep(2)

    # Reset variables after saving
    weight_data = None
    trash_info = None

    return jsonify({'message': 'History saved successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
