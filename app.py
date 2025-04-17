from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import os
import json
import subprocess
import uuid
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = 'YAMRAJ'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
if not os.path.exists('users.json'):
    with open('users.json', 'w') as f:
        json.dump({}, f)
if not os.path.exists('processes.json'):
    with open('processes.json', 'w') as f:
        json.dump({}, f)
if not os.path.exists('announcements.json'):
    with open('announcements.json', 'w') as f:
        json.dump([], f)

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin', False):
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with open('users.json', 'r') as f:
            users = json.load(f)
        
        if username in users:
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        users[username] = {
            'password': password,  # In production, use proper password hashing
            'is_admin': true  # First user becomes admin
        }
        
        # First user is admin
        if not users:
            users[username]['is_admin'] = True
        
        with open('users.json', 'w') as f:
            json.dump(users, f)
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with open('users.json', 'r') as f:
            users = json.load(f)
        
        if username not in users or users[username]['password'] != password:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))
        
        session['username'] = username
        session['is_admin'] = users[username].get('is_admin', False)
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], username)
    files = []
    
    if os.path.exists(user_dir):
        files = [f for f in os.listdir(user_dir) if f.endswith('.py')]
    
    # Get process status
    with open('processes.json', 'r') as f:
        processes = json.load(f)
    
    user_processes = {k: v for k, v in processes.items() if v['username'] == username}
    
    # Get announcements
    with open('announcements.json', 'r') as f:
        announcements = json.load(f)
    
    return render_template('dashboard.html', 
                         username=username,
                         files=files,
                         processes=user_processes,
                         announcements=announcements,
                         is_admin=session.get('is_admin', False))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(request.url)
    
    if file and file.filename.endswith('.py'):
        username = session['username']
        user_dir = os.path.join(app.config['UPLOAD_FOLDER'], username)
        os.makedirs(user_dir, exist_ok=True)
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(user_dir, filename)
        file.save(filepath)
        
        flash('File uploaded successfully', 'success')
    else:
        flash('Only Python files (.py) are allowed', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/start/<filename>')
def start_file(filename):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], username)
    filepath = os.path.join(user_dir, filename)
    
    if not os.path.exists(filepath):
        flash('File not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Generate unique process ID
    process_id = str(uuid.uuid4())
    
    # Create log file
    log_file = os.path.join(user_dir, f"{filename}.log")
    with open(log_file, 'a') as f:
        f.write(f"=== Starting process for {filename} ===\n")
    
    # Start the process
    try:
        process = subprocess.Popen(
            ['python', filepath],
            stdout=open(log_file, 'a'),
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Save process info
        with open('processes.json', 'r') as f:
            processes = json.load(f)
        
        processes[process_id] = {
            'pid': process.pid,
            'username': username,
            'filename': filename,
            'filepath': filepath,
            'log_file': log_file,
            'status': 'running'
        }
        
        with open('processes.json', 'w') as f:
            json.dump(processes, f)
        
        flash('Process started successfully', 'success')
    except Exception as e:
        flash(f'Error starting process: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/stop/<process_id>')
def stop_file(process_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    with open('processes.json', 'r') as f:
        processes = json.load(f)
    
    if process_id not in processes or processes[process_id]['username'] != session['username']:
        flash('Process not found or access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        # Stop the process
        subprocess.run(['kill', str(processes[process_id]['pid'])], check=True)
        
        # Update status
        processes[process_id]['status'] = 'stopped'
        
        # Log the stop
        with open(processes[process_id]['log_file'], 'a') as f:
            f.write(f"\n=== Process stopped by user ===\n")
        
        with open('processes.json', 'w') as f:
            json.dump(processes, f)
        
        flash('Process stopped successfully', 'success')
    except Exception as e:
        flash(f'Error stopping process: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/restart/<process_id>')
def restart_file(process_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    with open('processes.json', 'r') as f:
        processes = json.load(f)
    
    if process_id not in processes or processes[process_id]['username'] != session['username']:
        flash('Process not found or access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        # Stop the existing process if running
        if processes[process_id]['status'] == 'running':
            subprocess.run(['kill', str(processes[process_id]['pid'])], check=True)
        
        # Log the restart
        with open(processes[process_id]['log_file'], 'a') as f:
            f.write(f"\n=== Restarting process ===\n")
        
        # Start a new process
        process = subprocess.Popen(
            ['python', processes[process_id]['filepath']],
            stdout=open(processes[process_id]['log_file'], 'a'),
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Update process info
        processes[process_id]['pid'] = process.pid
        processes[process_id]['status'] = 'running'
        
        with open('processes.json', 'w') as f:
            json.dump(processes, f)
        
        flash('Process restarted successfully', 'success')
    except Exception as e:
        flash(f'Error restarting process: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/logs/<process_id>')
def view_logs(process_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    with open('processes.json', 'r') as f:
        processes = json.load(f)
    
    if process_id not in processes or processes[process_id]['username'] != session['username']:
        flash('Process not found or access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        with open(processes[process_id]['log_file'], 'r') as f:
            logs = f.read()
    except FileNotFoundError:
        logs = "No log file found"
    
    return render_template('logs.html', 
                         logs=logs,
                         filename=processes[process_id]['filename'],
                         status=processes[process_id]['status'])

@app.route('/admin')
@admin_required
def admin():
    with open('announcements.json', 'r') as f:
        announcements = json.load(f)
    
    with open('users.json', 'r') as f:
        users = json.load(f)
    
    with open('processes.json', 'r') as f:
        processes = json.load(f)
    
    return render_template('admin.html',
                         announcements=announcements,
                         users=users,
                         processes=processes)

@app.route('/admin/announce', methods=['POST'])
@admin_required
def make_announcement():
    message = request.form.get('message')
    if not message:
        flash('Message cannot be empty', 'danger')
        return redirect(url_for('admin'))
    
    with open('announcements.json', 'r') as f:
        announcements = json.load(f)
    
    announcements.insert(0, {
        'message': message,
        'author': session['username'],
        'timestamp': str(datetime.now())
    })
    
    # Keep only the last 10 announcements
    if len(announcements) > 10:
        announcements = announcements[:10]
    
    with open('announcements.json', 'w') as f:
        json.dump(announcements, f)
    
    flash('Announcement posted', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
