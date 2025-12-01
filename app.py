from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json
import os
from datetime import datetime
import secrets
import requests
from geopy.geocoders import Nominatim
from flask_mail import Mail, Message
from dotenv import load_dotenv
from cryptography.fernet import Fernet
web: gunicorn app:app


# ---- load env ----
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))

USERS_FILE = 'users.json'
CONTACTS_FILE = 'contacts.json'
HISTORY_FILE = 'history.json'

# --- Gmail SMTP Settings (FREE EMAIL EMERGENCY ALERTS) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

mail = Mail(app)

# --- Fast2SMS API Key (optional) ---
FAST2SMS_API_KEY = os.getenv('FAST2SMS_API_KEY', 'your-fast2sms-key-here')

# --- AES-style encryption key for location (Fernet) ---
FERNET_KEY = os.getenv('FERNET_KEY')
cipher = Fernet(FERNET_KEY.encode()) if FERNET_KEY else None


def init_files():
    for file in [USERS_FILE, CONTACTS_FILE, HISTORY_FILE]:
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump({} if file == USERS_FILE else [], f)
init_files()


def send_sms_fast2sms(message, numbers):
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = {
        'authorization': FAST2SMS_API_KEY,
        'sender_id': 'FSTSMS',
        'message': message,
        'language': 'english',
        'route': 'q',
        'numbers': numbers
    }
    headers = {
        'Content-Type': "application/x-www-form-urlencoded"
    }
    response = requests.post(url, data=payload, headers=headers)
    return response.json()


def send_email_alert(subject, recipients, body):
    if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
        return
    msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=recipients)
    msg.body = body
    mail.send(msg)


def get_place_name(lat, lon):
    geolocator = Nominatim(user_agent="women_safety_app")
    try:
        location = geolocator.reverse((lat, lon), language='en')
        if location and location.address:
            return location.address
    except Exception as e:
        print("Reverse geocoding error:", e)
    return f"Lat: {lat}, Lon: {lon}"


@app.route('/')
def welcome():
    if 'user' in session:
        return redirect(url_for('home'))
    return render_template('welcome.html')


@app.route('/signup')
def signup_page():
    return render_template('signup.html')


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template('home.html', user=session['user'])


@app.route('/contacts')
def contacts_page():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template('contacts.html')


@app.route('/history')
def history_page():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template('history.html')


@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)
    if data['email'] in users:
        return jsonify({'success': False, 'message': 'Email already exists'})
    users[data['email']] = {
        'name': data['name'],
        'phone': data['phone'],
        'email': data.get('email'),
        'password': data['password']
    }
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)
    session['user'] = data['email']
    return jsonify({'success': True})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)
    if data['email'] not in users or users[data['email']]['password'] != data['password']:
        return jsonify({'success': False, 'message': 'Invalid credentials'})
    session['user'] = data['email']
    return jsonify({'success': True})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True})


@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    if 'user' not in session:
        return jsonify([])
    with open(CONTACTS_FILE, 'r') as f:
        all_contacts = json.load(f)
    user_contacts = [c for c in all_contacts if c.get('user') == session['user']]
    return jsonify(user_contacts)


@app.route('/api/contacts', methods=['POST'])
def add_contact():
    if 'user' not in session:
        return jsonify({'success': False})
    data = request.json
    contact = {
        'id': datetime.now().timestamp(),
        'user': session['user'],
        'name': data['name'],
        'phone': data['phone'],
        'email': data.get('email'),
        'relationship': data['relationship']
    }
    with open(CONTACTS_FILE, 'r') as f:
        contacts = json.load(f)
    contacts.append(contact)
    with open(CONTACTS_FILE, 'w') as f:
        json.dump(contacts, f)
    return jsonify(contact)


@app.route('/api/contacts/<float:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    with open(CONTACTS_FILE, 'r') as f:
        contacts = json.load(f)
    contacts = [c for c in contacts
                if c['id'] != contact_id or c.get('user') != session.get('user')]
    with open(CONTACTS_FILE, 'w') as f:
        json.dump(contacts, f)
    return jsonify({'success': True})


@app.route('/api/contacts/<float:contact_id>', methods=['PUT'])
def edit_contact(contact_id):
    if 'user' not in session:
        return jsonify({'success': False})
    data = request.json
    with open(CONTACTS_FILE, 'r') as f:
        contacts = json.load(f)
    for contact in contacts:
        if contact['id'] == contact_id and contact.get('user') == session['user']:
            contact['name'] = data['name']
            contact['phone'] = data['phone']
            contact['email'] = data['email']
            contact['relationship'] = data['relationship']
    with open(CONTACTS_FILE, 'w') as f:
        json.dump(contacts, f)
    return jsonify({'success': True})


@app.route('/api/history', methods=['GET'])
def get_history():
    if 'user' not in session:
        return jsonify([])
    with open(HISTORY_FILE, 'r') as f:
        all_history = json.load(f)
    user_history = [h for h in all_history if h.get('user') == session['user']]

    # decrypt encrypted location field if present
    if cipher:
        for h in user_history:
            if h.get('location_enc'):
                try:
                    h['location'] = cipher.decrypt(
                        h['location_enc'].encode()
                    ).decode()
                except Exception:
                    h['location'] = 'Unknown'
    return jsonify(user_history)


def _send_sos_common(place_name, maps_link, alert_type_label):
    with open(CONTACTS_FILE, 'r') as f:
        all_contacts = json.load(f)
    user_contacts = [c for c in all_contacts if c.get('user') == session['user']]
    phone_numbers = ','.join(
        [c['phone'][-10:] for c in user_contacts
         if c.get('phone') and len(c['phone']) >= 10]
    )

    sos_message = (
        f"EMERGENCY SOS! User {session['user']} needs help! {alert_type_label}\n"
        f"Location: {place_name}\n"
        f"Navigate: {maps_link}\n"
    )

    email_subject = f"EMERGENCY SOS Alert! {alert_type_label}"
    email_body = (
        f"User {session['user']} needs help! {alert_type_label}\n"
        f"Location: {place_name}\n"
        f"Navigate: {maps_link}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "Please respond urgently."
    )
    email_recipients = [c['email'] for c in user_contacts if c.get('email')]

    if email_recipients:
        send_email_alert(email_subject, email_recipients, email_body)

    if phone_numbers and FAST2SMS_API_KEY and FAST2SMS_API_KEY != 'your-fast2sms-key-here':
        sms_result = send_sms_fast2sms(sos_message, phone_numbers)
        print("Fast2SMS Response:", sms_result)
    else:
        sms_result = {'error': 'No contacts to notify or SMS disabled.'}

    # encrypt location for storage
    if cipher:
        enc = cipher.encrypt(place_name.encode()).decode()
        store_location = None
        store_location_enc = enc
    else:
        store_location = place_name
        store_location_enc = None

    alert = {
        'id': datetime.now().timestamp(),
        'user': session['user'],
        'timestamp': datetime.now().isoformat(),
        'location': store_location,          # may be None
        'location_enc': store_location_enc,  # encrypted value
        'contacts_notified': len(user_contacts),
        'type': alert_type_label.strip()
    }
    with open(HISTORY_FILE, 'r') as f:
        history = json.load(f)
    history.insert(0, alert)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

    return alert, sms_result


@app.route('/api/sos', methods=['POST'])
def trigger_sos():
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    data = request.json
    loc = data.get('location', {})
    lat, lon = None, None

    if isinstance(loc, dict):
        lat = loc.get('lat')
        lon = loc.get('lon')
    elif isinstance(loc, str):
        try:
            lat_str, lon_str = loc.split(",")
            lat = float(lat_str.strip())
            lon = float(lon_str.strip())
        except Exception:
            lat, lon = None, None

    if lat is not None and lon is not None:
        place_name = get_place_name(lat, lon)
        maps_link = f"https://maps.google.com/?q={lat},{lon}"
    else:
        place_name = 'Unknown'
        maps_link = ''

    alert, sms_result = _send_sos_common(place_name, maps_link, 'SOS')
    return jsonify({
        'success': True,
        'message': f'SOS sent to {alert["contacts_notified"]} contacts!',
        'alert': alert,
        'sms_result': sms_result
    })


@app.route('/api/sos-offline', methods=['POST'])
def sos_offline():
    """
    Accepts payload from frontend queue:
    { "location": { "lat": ..., "lon": ... }, "source": "manual"/"ai", "timestamp": "ISO" }
    """
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401

    data = request.get_json() or {}
    loc = data.get('location', {}) or {}
    lat = loc.get('lat')
    lon = loc.get('lon')

    if lat is not None and lon is not None:
        place_name = get_place_name(lat, lon)
        maps_link = f"https://maps.google.com/?q={lat},{lon}"
    else:
        place_name = 'Unknown'
        maps_link = ''

    src = data.get('source', 'manual').upper()
    label = f"(Queued / {src})"

    alert, sms_result = _send_sos_common(place_name, maps_link, label)
    return jsonify({
        'success': True,
        'message': f'Queued SOS processed and sent to {alert["contacts_notified"]} contacts!',
        'alert': alert,
        'sms_result': sms_result
    })


if __name__ == '__main__':
    print("\n🚀 Women Safety App is running!")
    print("📱 Open: http://localhost:5000")
    print("🛑 Press Ctrl+C to stop\n")
    app.run(debug=True, host="0.0.0.0", port=5000)

