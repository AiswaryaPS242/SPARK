from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for flashing messages

# Hardcoded user credentials for demonstration purposes
USER_CREDENTIALS = {
    'admin': {
        'password': 'password123',
        'semester': 'None',
        'person_type': 'None',
        'learner_type': 'None'
    }
}

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in USER_CREDENTIALS and password == USER_CREDENTIALS[username]['password']:
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))  # Redirect to a dashboard page
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        semester = request.form['semester']
        person_type = request.form['person_type']
        learner_type = request.form['learner_type']

        if username in USER_CREDENTIALS:
            flash('Username already exists', 'error')
        else:
            USER_CREDENTIALS[username] = {
                'password': password,
                'semester': semester,
                'person_type': person_type,
                'learner_type': learner_type
            }
            flash('Account created successfully!', 'success')
            return redirect(url_for('login'))

    return render_template('create_account.html')

@app.route('/dashboard')
def dashboard():
    return 'Welcome to the Dashboard!'

if __name__ == '__main__':
    app.run(debug=True)                                                                                                        