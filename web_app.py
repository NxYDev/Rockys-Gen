from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import secrets
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)

# Configuration
CONFIG_FILE = 'config.json'
ACCOUNTS_DB = 'accounts.json'
STATS_DB = 'stats.json'

# Default configuration with auto-generated secret key
DEFAULT_CONFIG = {
    "web": {
        "host": "0.0.0.0",
        "port": 5000,
        "secret_key": secrets.token_hex(32),
        "username": "admin",
        "password": generate_password_hash("admin123")  # Default password
    }
}

# Helper functions
def load_config():
    """Load or create configuration file"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure all web settings exist
            if 'web' not in config:
                config['web'] = DEFAULT_CONFIG['web']
            return config
    # Create new config with defaults
    with open(CONFIG_FILE, 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def load_accounts():
    """Load accounts database"""
    if os.path.exists(ACCOUNTS_DB):
        with open(ACCOUNTS_DB, 'r') as f:
            return json.load(f)
    return {"free": {}, "premium": {}}

def load_stats():
    """Load statistics"""
    if os.path.exists(STATS_DB):
        with open(STATS_DB, 'r') as f:
            return json.load(f)
    return {"free_generated": 0, "premium_generated": 0, "accounts_added": 0}

# Load configuration
config = load_config()
app.secret_key = config['web']['secret_key']

# Create default templates
def create_templates():
    templates_dir = 'templates'
    os.makedirs(templates_dir, exist_ok=True)
    
    templates = {
        'base.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Account Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        .sidebar {
            transition: all 0.3s;
        }
        @media (max-width: 768px) {
            .sidebar {
                transform: translateX(-100%);
            }
            .sidebar.active {
                transform: translateX(0);
            }
        }
    </style>
</head>
<body class="bg-gray-900 text-gray-100">
    <div class="flex h-screen">
        <!-- Sidebar -->
        <div class="sidebar fixed md:relative w-64 bg-gray-800 h-full z-10">
            <div class="p-4 border-b border-gray-700">
                <h1 class="text-xl font-bold">Account Generator</h1>
            </div>
            <nav class="p-4">
                <ul>
                    <li class="mb-2">
                        <a href="{{ url_for('dashboard') }}" class="block px-4 py-2 rounded hover:bg-gray-700 {{ 'bg-gray-700' if request.path == url_for('dashboard') }}">
                            <i class="fas fa-tachometer-alt mr-2"></i> Dashboard
                        </a>
                    </li>
                    <li class="mb-2">
                        <a href="{{ url_for('accounts') }}" class="block px-4 py-2 rounded hover:bg-gray-700 {{ 'bg-gray-700' if request.path == url_for('accounts') }}">
                            <i class="fas fa-user-shield mr-2"></i> Account Management
                        </a>
                    </li>
                    <li class="mb-2">
                        <a href="{{ url_for('settings') }}" class="block px-4 py-2 rounded hover:bg-gray-700 {{ 'bg-gray-700' if request.path == url_for('settings') }}">
                            <i class="fas fa-cog mr-2"></i> Settings
                        </a>
                    </li>
                    <li>
                        <a href="{{ url_for('logout') }}" class="block px-4 py-2 rounded hover:bg-gray-700">
                            <i class="fas fa-sign-out-alt mr-2"></i> Logout
                        </a>
                    </li>
                </ul>
            </nav>
        </div>
        
        <!-- Main content -->
        <div class="flex-1 overflow-auto">
            <!-- Mobile menu button -->
            <button class="md:hidden fixed top-4 left-4 z-20 bg-gray-800 p-2 rounded" onclick="toggleSidebar()">
                <i class="fas fa-bars"></i>
            </button>
            
            <div class="p-6">
                <!-- Flash messages -->
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="mb-4 p-4 rounded {{ 'bg-green-800' if category == 'success' else 'bg-red-800' }}">
                                {{ message }}
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}
                
                {% block content %}{% endblock %}
            </div>
        </div>
    </div>
    
    <script>
        function toggleSidebar() {
            document.querySelector('.sidebar').classList.toggle('active');
        }
    </script>
</body>
</html>''',
        'login.html': '''{% extends "base.html" %}

{% block content %}
<div class="max-w-md mx-auto mt-10">
    <div class="bg-gray-800 p-8 rounded-lg shadow-lg">
        <h2 class="text-2xl font-bold mb-6 text-center">Admin Login</h2>
        <form method="POST" action="{{ url_for('login') }}">
            <div class="mb-4">
                <label for="username" class="block mb-2">Username</label>
                <input type="text" id="username" name="username" class="w-full px-3 py-2 bg-gray-700 rounded" required>
            </div>
            <div class="mb-6">
                <label for="password" class="block mb-2">Password</label>
                <input type="password" id="password" name="password" class="w-full px-3 py-2 bg-gray-700 rounded" required>
            </div>
            <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 py-2 px-4 rounded font-bold">
                Login
            </button>
        </form>
    </div>
</div>
{% endblock %}''',
        'dashboard.html': '''{% extends "base.html" %}

{% block content %}
<h1 class="text-3xl font-bold mb-6">Dashboard</h1>

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
    <div class="bg-gray-800 p-6 rounded-lg">
        <h3 class="text-xl font-semibold mb-2">Free Accounts</h3>
        <p class="text-3xl font-bold text-blue-400">{{ stats.free }}</p>
    </div>
    <div class="bg-gray-800 p-6 rounded-lg">
        <h3 class="text-xl font-semibold mb-2">Premium Accounts</h3>
        <p class="text-3xl font-bold text-yellow-400">{{ stats.premium }}</p>
    </div>
    <div class="bg-gray-800 p-6 rounded-lg">
        <h3 class="text-xl font-semibold mb-2">Free Generated</h3>
        <p class="text-3xl font-bold text-green-400">{{ total_stats.free_generated }}</p>
    </div>
    <div class="bg-gray-800 p-6 rounded-lg">
        <h3 class="text-xl font-semibold mb-2">Premium Generated</h3>
        <p class="text-3xl font-bold text-purple-400">{{ total_stats.premium_generated }}</p>
    </div>
</div>

<div class="bg-gray-800 p-6 rounded-lg mb-8">
    <h2 class="text-2xl font-bold mb-4">Services Overview</h2>
    <div class="overflow-x-auto">
        <table class="w-full">
            <thead>
                <tr class="border-b border-gray-700">
                    <th class="py-2 text-left">Service</th>
                    <th class="py-2 text-right">Free</th>
                    <th class="py-2 text-right">Premium</th>
                    <th class="py-2 text-right">Total</th>
                </tr>
            </thead>
            <tbody>
                {% for service, counts in stats.services.items() %}
                <tr class="border-b border-gray-700 hover:bg-gray-700">
                    <td class="py-3">{{ service }}</td>
                    <td class="py-3 text-right">{{ counts.free }}</td>
                    <td class="py-3 text-right">{{ counts.premium }}</td>
                    <td class="py-3 text-right">{{ counts.free + counts.premium }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}''',
        'accounts.html': '''{% extends "base.html" %}

{% block content %}
<h1 class="text-3xl font-bold mb-6">Account Management</h1>

<div class="bg-gray-800 p-6 rounded-lg mb-8">
    <h2 class="text-2xl font-bold mb-4">Add Accounts</h2>
    <form method="POST" action="{{ url_for('upload_accounts') }}" enctype="multipart/form-data">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
                <label for="account_type" class="block mb-2">Account Type</label>
                <select id="account_type" name="account_type" class="w-full px-3 py-2 bg-gray-700 rounded" required>
                    <option value="free">Free</option>
                    <option value="premium">Premium</option>
                </select>
            </div>
            <div>
                <label for="service" class="block mb-2">Service Name</label>
                <input type="text" id="service" name="service" class="w-full px-3 py-2 bg-gray-700 rounded" required>
            </div>
            <div>
                <label for="accounts" class="block mb-2">Accounts File</label>
                <input type="file" id="accounts" name="accounts" class="w-full px-3 py-2 bg-gray-700 rounded" accept=".txt" required>
            </div>
        </div>
        <button type="submit" class="bg-green-600 hover:bg-green-700 py-2 px-4 rounded font-bold">
            Upload Accounts
        </button>
    </form>
</div>

<div class="bg-gray-800 p-6 rounded-lg">
    <h2 class="text-2xl font-bold mb-4">Current Stock</h2>
    <div class="mb-6">
        <h3 class="text-xl font-semibold mb-2">Free Accounts</h3>
        {% if free_services %}
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {% for service, count in free_services.items() %}
                <div class="bg-gray-700 p-4 rounded">
                    <div class="flex justify-between items-center">
                        <span>{{ service }}</span>
                        <span class="bg-blue-600 text-white px-2 py-1 rounded text-sm">{{ count }} available</span>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <p class="text-gray-400">No free accounts available</p>
        {% endif %}
    </div>
    
    <div>
        <h3 class="text-xl font-semibold mb-2">Premium Accounts</h3>
        {% if premium_services %}
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {% for service, count in premium_services.items() %}
                <div class="bg-gray-700 p-4 rounded">
                    <div class="flex justify-between items-center">
                        <span>{{ service }}</span>
                        <span class="bg-yellow-600 text-white px-2 py-1 rounded text-sm">{{ count }} available</span>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <p class="text-gray-400">No premium accounts available</p>
        {% endif %}
    </div>
</div>
{% endblock %}''',
        'settings.html': '''{% extends "base.html" %}

{% block content %}
<h1 class="text-3xl font-bold mb-6">Settings</h1>

<div class="bg-gray-800 p-6 rounded-lg">
    <h2 class="text-2xl font-bold mb-4">Web Panel Settings</h2>
    <form method="POST" action="{{ url_for('update_web_settings') }}">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
                <label for="web_username" class="block mb-2">Username</label>
                <input type="text" id="web_username" name="web_username" value="{{ config.web.username }}" class="w-full px-3 py-2 bg-gray-700 rounded" required>
            </div>
            <div>
                <label for="web_password" class="block mb-2">Password (leave blank to keep current)</label>
                <input type="password" id="web_password" name="web_password" class="w-full px-3 py-2 bg-gray-700 rounded">
            </div>
        </div>
        
        <button type="submit" class="bg-blue-600 hover:bg-blue-700 py-2 px-4 rounded font-bold">
            Save Settings
        </button>
    </form>
</div>
{% endblock %}'''
    }

    for name, content in templates.items():
        path = os.path.join(templates_dir, name)
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write(content)

# Routes
@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Debug output
        print(f"Login attempt: {username}")
        print(f"Stored username: {config['web']['username']}")
        print(f"Password match: {check_password_hash(config['web']['password'], password)}")
        
        if (username == config['web']['username'] and 
            check_password_hash(config['web']['password'], password)):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            print("Login failed - invalid credentials")
            flash('Invalid username or password', 'error')
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    accounts = load_accounts()
    stats = {
        "free": 0,
        "premium": 0,
        "services": {}
    }
    
    # Calculate account statistics
    for acc_type in ["free", "premium"]:
        for service, acc_list in accounts[acc_type].items():
            available = sum(1 for acc in acc_list if not acc.get("used", False))
            if available > 0:
                if service not in stats["services"]:
                    stats["services"][service] = {"free": 0, "premium": 0}
                stats["services"][service][acc_type] = available
                stats[acc_type] += available
    
    total_stats = load_stats()
    
    return render_template(
        'dashboard.html',
        title='Dashboard',
        stats=stats,
        total_stats=total_stats
    )

@app.route('/accounts')
def accounts():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    accounts = load_accounts()
    free_services = {}
    premium_services = {}
    
    for service, acc_list in accounts["free"].items():
        count = sum(1 for acc in acc_list if not acc.get("used", False))
        if count > 0:
            free_services[service] = count
            
    for service, acc_list in accounts["premium"].items():
        count = sum(1 for acc in acc_list if not acc.get("used", False))
        if count > 0:
            premium_services[service] = count
    
    return render_template(
        'accounts.html',
        title='Account Management',
        free_services=free_services,
        premium_services=premium_services
    )

@app.route('/upload-accounts', methods=['POST'])
def upload_accounts():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    account_type = request.form.get('account_type')
    service = request.form.get('service')
    file = request.files.get('accounts')
    
    if not file or not file.filename.endswith('.txt'):
        flash('Please upload a valid .txt file', 'error')
        return redirect(url_for('accounts'))
    
    try:
        accounts_list = file.read().decode('utf-8').splitlines()
        accounts_list = [acc.strip() for acc in accounts_list if acc.strip()]
        
        accounts = load_accounts()
        if service not in accounts[account_type]:
            accounts[account_type][service] = []
            
        accounts[account_type][service].extend([{
            "credentials": acc,
            "used": False,
            "used_by": None,
            "used_at": None
        } for acc in accounts_list])
        
        save_accounts(accounts)
        
        # Update stats
        stats = load_stats()
        stats["accounts_added"] += len(accounts_list)
        save_stats(stats)
        
        flash(f'Successfully added {len(accounts_list)} {account_type} accounts for {service}', 'success')
    except Exception as e:
        flash('An error occurred while processing the file', 'error')
        
    return redirect(url_for('accounts'))

@app.route('/settings')
def settings():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    return render_template('settings.html', title='Settings', config=config)

@app.route('/update-web-settings', methods=['POST'])
def update_web_settings():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    config['web']['username'] = request.form.get('web_username')
    new_password = request.form.get('web_password')
    if new_password:
        config['web']['password'] = generate_password_hash(new_password)
    
    save_config(config)
    flash('Web panel settings updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    create_templates()
    
    # Print login information
    print("\n" + "="*50)
    print(f"Web Panel Login Information:")
    print(f"URL: http://{config['web']['host']}:{config['web']['port']}")
    print(f"Username: {config['web']['username']}")
    print(f"Password: admin123 (default)")
    print("="*50 + "\n")
    

print("\nRESETTING CREDENTIALS TO DEFAULT!")
config['web']['username'] = "admin"
config['web']['password'] = generate_password_hash("admin123")  # Reset to known password
save_config(config)
print("Credentials have been reset to: admin/admin123")

app.run(
    host=config['web']['host'],
    port=config['web']['port'],
    debug=True
)