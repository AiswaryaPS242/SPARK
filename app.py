from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management and flashing messages

# Dummy user database (for demonstration purposes)
users = {}

# Dummy subject data for each semester (from the syllabus)
subjects_by_semester = {
    3: [
        "MAT 203: DISCRETE MATHEMATICAL STRUCTURES",
        "CST 201: DATA STRUCTURES",
        "CST 203: LOGIC SYSTEM DESIGN",
        "CST 205: OBJECT ORIENTED PROGRAMMING USING JAVA"
    ],
    4: [
        "MAT256: PROBABILITY AND STATISTICAL MODELLING",
        "CST202: COMPUTER ORGANISATION AND ARCHITECTURE",
        "CST 204: DATABASE MANAGEMENT SYSTEMS",
        "CST 206: OPERATING SYSTEMS"
    ],
    5: [
        "ADT301 FOUNDATIONS OF DATA SCIENCE",
        "CST 303 COMPUTER NETWORKS",
        "AMT 305 INTRODUCTION TO MACHINE LEARNING",
        "AIT307 INTRODUCTION TO ARTIFICIAL INTELLIGENCE"
    ],
    6: [
        "ADT 302: Concepts in Big Data Analytics",
        "AIT 304: Robotics and Intelligent Systems",
        "CST 306: Algorithm Analysis and Design",
        "AIT 352: Artificial Neural Networks Techniques",
        "AIT 362: Programming in R",
        "AIT 322: Concepts in Computer Graphics and Image Processing"
    ],
    7: [
        "AIT 401: Foundations of Deep Learning",
        "AIT 413: Advanced Concepts of Microprocessor and Microcontroller",
        "CST 423: Cloud Computing",
        "CST 433: Security in Computing",
        "AIT 443: Concepts in Compiler Design",
        "ADT 453: Information Extraction and Retrieval",
        "CST 463: Web Programming",
        "CST 473: Natural Language Processing",
        "CST 415: Introduction to Mobile Computing",
        "CST 425: Introduction to Deep Learning",
        "CST 435: Computer Graphics",
        "CST 445: Python for Engineers",
        "CST 455: Object-Oriented Concepts"
    ],
    8: [
        "ADT 402: Business Analytics",
        "AMT 414: GPU Computing",
        "CST 424: Programming Paradigms",
        "CST 434: Network Security Protocols",
        "CST 444: Soft Computing",
        "CST 454: Fuzzy Set Theory and Applications",
        "CST 464: Embedded Systems",
        "CST 474: Computer Vision",
        "AMT 416: Human-Computer Interaction",
        "AIT 426: Mining of Massive Data Sets",
        "CST 436: Parallel Computing",
        "CST 446: Data Compression Techniques",
        "AIT 456: Introduction to Reinforcement Learning",
        "CST 466: Data Mining",
        "AIT 476: Bio-Inspired Optimization Techniques",
        "CST 418: High-Performance Computing",
        "CST 428: Blockchain Technologies",
        "CST 438: Image Processing Techniques",
        "CST 448: Internet of Things",
        "CST 458: Software Testing",
        "CST 468: Bioinformatics",
        "CST 478: Computational Linguistics"
    ]
}

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the user exists and the password is correct
        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['semester'] = users[username]['semester']  # Store semester in session
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
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

        # Store user data in the dummy database
        users[username] = {
            'password': password,
            'semester': int(semester),
            'person_type': person_type,
            'learner_type': learner_type
        }

        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('create_account.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash('Please login to access the dashboard.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    semester = session['semester']
    subjects = subjects_by_semester.get(semester, [])

    return render_template('dashboard.html', username=username, semester=semester, subjects=subjects)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('semester', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)