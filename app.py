from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import numpy as np
import random
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this for production security

# PostgreSQL Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgre20@localhost/spark'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    person_type = db.Column(db.String(20), nullable=False)  # 'morning' or 'night'
    learner_type = db.Column(db.String(20), nullable=False)  # 'fast' or 'slow'
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    selected_subjects = db.relationship('SelectedSubject', backref='user', lazy=True)
    exam_dates = db.relationship('ExamDate', backref='user', lazy=True)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    code = db.Column(db.String(20), nullable=True)
    selected_by = db.relationship('SelectedSubject', backref='subject', lazy=True)
    modules = db.relationship('Module', backref='subject', lazy=True)

class Module(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    completed_by = db.relationship('CompletedModule', backref='module', lazy=True)

class SelectedSubject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    date_selected = db.Column(db.DateTime, default=datetime.utcnow)

class CompletedModule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=False)
    date_completed = db.Column(db.DateTime, default=datetime.utcnow)

class ExamDate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200), nullable=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='tasks')

# Reinforcement Learning Environment
class StudyScheduleEnv:
    def __init__(self, user, subjects, exam_dates):
        self.user = user
        self.subjects = subjects
        self.exam_dates = exam_dates
        self.modules = self._get_all_modules()
        self.state_size = len(self.modules) + 2  # Modules + days_remaining + learner_type
        self.action_size = len(self.modules)  # Each action corresponds to a module
        self.reset()

    def _get_all_modules(self):
        modules = []
        for subject in self.subjects:
            modules.extend(subject.modules)
        return modules

    def reset(self):
        self.current_progress = {module.id: False for module in self.modules}  # Track module completion
        # Handle empty exam_dates
        if self.exam_dates:
            self.days_remaining = (self.exam_dates[0].exam_date - datetime.today().date()).days
        else:
            self.days_remaining = 30  # Default to 30 days if no exam dates are available
        self.state = self._get_state()
        return self.state

    def _get_state(self):
        # State representation: [module_completion_status, days_remaining, learner_type]
        module_status = [int(self.current_progress[module.id]) for module in self.modules]
        learner_type = 0 if self.user.learner_type == 'slow' else 1
        state = module_status + [self.days_remaining, learner_type]
        return np.array(state)

    def step(self, action):
        module = self.modules[action]
        reward = 0

        # Mark module as completed
        if not self.current_progress[module.id]:
            self.current_progress[module.id] = True
            reward += 10  # Positive reward for completing a module

        # Check if all modules are completed
        if all(self.current_progress.values()):
            reward += 100  # Large reward for completing all modules
            done = True
        else:
            done = False

        # Penalize for each passing day
        self.days_remaining -= 1
        if self.days_remaining < 0:
            reward -= 50  # Negative reward for missing the deadline
            done = True

        next_state = self._get_state()
        return next_state, reward, done

# Q-Learning Agent
class QLearningAgent:
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.q_table = defaultdict(lambda: np.zeros(action_size))
        self.learning_rate = 0.1
        self.discount_factor = 0.99
        self.epsilon = 1.0
        self.epsilon_decay = 0.995
        self.epsilon_min = 0.01

    def get_action(self, state):
        if np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)
        else:
            return np.argmax(self.q_table[tuple(state)])

    def update_q_table(self, state, action, reward, next_state, done):
        state = tuple(state)
        next_state = tuple(next_state)
        q_value = self.q_table[state][action]
        next_q_value = np.max(self.q_table[next_state])

        # Update Q-value using Bellman equation
        new_q_value = q_value + self.learning_rate * (reward + self.discount_factor * next_q_value - q_value)
        self.q_table[state][action] = new_q_value

        # Decay epsilon
        if done:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

# Train the RL Agent
def train_rl_agent(user, subjects, exam_dates, episodes=1000):
    env = StudyScheduleEnv(user, subjects, exam_dates)
    agent = QLearningAgent(env.state_size, env.action_size)

    for episode in range(episodes):
        state = env.reset()
        done = False
        total_reward = 0

        while not done:
            action = agent.get_action(state)
            next_state, reward, done = env.step(action)
            agent.update_q_table(state, action, reward, next_state, done)
            state = next_state
            total_reward += reward

        print(f"Episode: {episode + 1}, Total Reward: {total_reward}")

    return agent


# Create database tables and populate with initial data
def init_db():
    with app.app_context():
        # Create all tables
        db.create_all()
       
        # Check if subjects already exist
        if Subject.query.first() is None:
            # Add subjects from your existing data
            subjects_by_semester = {
                3: [
                    "MAT 203: DISCRETE MATHEMATICAL STRUCTURES",
                    "CST 201: DATA STRUCTURES",
                    "CST 203: LOGIC SYSTEM DESIGN",
                    "CST 205: OBJECT ORIENTED PROGRAMMING USING JAVA"
                ],
                # ... (Include all other semesters from your original code)
                4: [
                    "MAT 256: PROBABILITY AND STATISTICAL MODELLING",
                    "CST 202: COMPUTER ORGANISATION AND ARCHITECTURE",
                    "CST 204: DATABASE MANAGEMENT SYSTEMS",
                    "CST 206: OPERATING SYSTEMS"
                ],
                5: [
                    "ADT 301: FOUNDATIONS OF DATA SCIENCE",
                    "CST 303: COMPUTER NETWORKS",
                    "AMT 305: INTRODUCTION TO MACHINE LEARNING",
                    "AIT 307: INTRODUCTION TO ARTIFICIAL INTELLIGENCE"
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
           
            for semester, subject_list in subjects_by_semester.items():
                for subject_name in subject_list:
                    # Extract code if available
                    code = None
                    if ":" in subject_name:
                        parts = subject_name.split(":", 1)
                        code = parts[0].strip()
                        name = parts[1].strip()
                    else:
                        # Try to extract code if in format like "CST 201 DATA STRUCTURES"
                        parts = subject_name.split(" ", 2)
                        if len(parts) >= 3 and parts[0].isalpha() and parts[1].isdigit():
                            code = f"{parts[0]} {parts[1]}"
                            name = parts[2]
                        else:
                            name = subject_name
                   
                    subject = Subject(name=name, semester=semester, code=code)
                    db.session.add(subject)
                   
                    # Add default modules for each subject
                    for i in range(1, 6):
                        module = Module(name=f"Module {i}", subject=subject)
                        db.session.add(module)
           
            # Create admin user
            admin = User(
                username="admin",
                password=generate_password_hash("admin123"),
                semester=8,  # Default semester for admin
                person_type="morning",
                learner_type="fast",
                is_admin=True
            )
            db.session.add(admin)
           
            # Commit all changes
            db.session.commit()
            print("Database initialized with subjects and admin user.")

# Modified routes to use the database
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
       
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['semester'] = user.semester
            session['is_admin'] = user.is_admin
           
            flash('Login successful!', 'success')
           
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        semester = int(request.form['semester'])
        person_type = request.form['person_type']
        learner_type = request.form['learner_type']

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose another one.', 'error')
            return render_template('create_account.html')
       
        # Create new user
        new_user = User(
            username=username,
            password=generate_password_hash(password),
            semester=semester,
            person_type=person_type,
            learner_type=learner_type
        )
       
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('create_account.html')


# Route for the Exam Date Selection Dashboard
@app.route('/exam_dashboard')
def exam_dashboard():
    if 'user_id' not in session:
        flash('Please login to access the exam dashboard.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    if not user:
        session.clear()
        flash('User not found. Please login again.', 'error')
        return redirect(url_for('login'))

    # Get subjects for user's semester
    subjects = Subject.query.filter_by(semester=user.semester).all()

    # Get user's selected subjects
    selected_subjects = SelectedSubject.query.filter_by(user_id=user_id).all()
    selected_subject_ids = [s.subject_id for s in selected_subjects]

    # Get user's exam dates
    exam_dates = ExamDate.query.filter_by(user_id=user_id).all()

    return render_template(
        'exam_dashboard.html',
        username=user.username,
        semester=user.semester,
        subjects=subjects,
        selected_subject_ids=selected_subject_ids,
        exam_dates=exam_dates
    )

# Route for the To-Do List Page
@app.route('/todo')
def todo():
    if 'user_id' not in session:
        flash('Please login to access the to-do list.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.due_date.asc()).all()

    return render_template(
        'todo.html',
        username=session['username'],
        tasks=tasks
    )

# Route for the Home Page
@app.route('/home')
def home():
    if 'user_id' not in session:
        flash('Please login to access the home page.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        session.clear()
        flash('User not found. Please login again.', 'error')
        return redirect(url_for('login'))

    # Get all tasks (including study plan tasks)
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.due_date.asc()).all()

    # Debug: Print all tasks
    print(f"All Tasks: {tasks}")

    # Get study plan tasks (filter by tasks with titles starting with "Study")
    study_plan_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.title.like("Study%")  # Filter tasks with titles starting with "Study"
    ).order_by(Task.due_date.asc()).all()

    # Debug: Print study plan tasks
    print(f"Study Plan Tasks: {study_plan_tasks}")

    return render_template(
        'home.html',
        username=user.username,
        tasks=tasks,
        study_plan_tasks=study_plan_tasks
    )

@app.route('/study_plan')
def study_plan():
    if 'user_id' not in session:
        flash('Please login to view your study plan.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        session.clear()
        flash('User not found. Please login again.', 'error')
        return redirect(url_for('login'))

    # Get the user's selected subjects and exam dates
    selected_subjects = SelectedSubject.query.filter_by(user_id=user_id).all()
    exam_dates = ExamDate.query.filter_by(user_id=user_id).all()

    # Debug: Print selected subjects and exam dates
    print(f"Selected Subjects: {selected_subjects}")
    print(f"Exam Dates: {exam_dates}")

    if not selected_subjects or not exam_dates:
        flash('Please select subjects and exam dates first.', 'error')
        return redirect(url_for('exam_dashboard'))

    # Clear existing study plan tasks
    Task.query.filter(
        Task.user_id == user_id,
        Task.title.like("Study%")  # Filter tasks with titles starting with "Study"
    ).delete()

    # Generate study schedule for selected modules of selected subjects
    study_schedule = []
    current_date = datetime.today().date()

    for selected_subject in selected_subjects:
        subject = Subject.query.get(selected_subject.subject_id)
        if subject:
            # Get the exam date for this subject
            exam_date_record = next((ed for ed in exam_dates if ed.subject_id == subject.id), None)
            exam_date = exam_date_record.exam_date if exam_date_record else (current_date + timedelta(days=30))

            # Debug: Print subject and exam date
            print(f"Subject: {subject.name}, Exam Date: {exam_date}")

            # Get selected modules for this subject
            selected_modules = (
                db.session.query(Module)
                .join(CompletedModule, CompletedModule.module_id == Module.id)
                .filter(CompletedModule.user_id == user_id, Module.subject_id == subject.id)
                .all()
            )

            # Debug: Print selected modules
            print(f"Selected Modules for Subject {subject.name}: {[m.name for m in selected_modules]}")

            # Generate study schedule for selected modules
            for module in selected_modules:
                # Debug: Print module info
                print(f"Module: {module.name}, Subject: {subject.name}")

                # Calculate days before exam for spacing
                days_before_exam = (exam_date - current_date).days
                days_per_module = max(1, days_before_exam // len(selected_modules)) if selected_modules else 1

                # Add this module to the study schedule
                study_date = current_date + timedelta(days=len(study_schedule))
                # Ensure we're not scheduling too close to the exam
                if (exam_date - study_date).days < 2:
                    study_date = exam_date - timedelta(days=2)

                study_schedule.append({
                    'date': study_date,
                    'module': module.name,
                    'subject': subject.name,
                    'subject_id': subject.id,
                    'is_completed': False  # Since we're only adding incomplete modules
                })

    # Debug: Print study schedule
    print(f"Study Schedule: {study_schedule}")

    # Sort study schedule by date
    study_schedule.sort(key=lambda x: x['date'])

    # Add tasks to the database
    for task in study_schedule:
        # Calculate start and end times based on user preferences
        if user.person_type == 'morning':
            start_time = '08:00'
            end_time = '10:00'
        else:
            start_time = '20:00'
            end_time = '22:00'

        # Adjust for slow learners
        if user.learner_type == 'slow':
            # Just for description purposes
            adjusted_end_time = datetime.strptime(end_time, '%H:%M') + timedelta(hours=1)
            end_time = adjusted_end_time.strftime('%H:%M')

        # Add task to the database
        new_task = Task(
            user_id=user_id,
            title=f"Study {task['subject']} - {task['module']}",
            description=f"Complete {task['module']} for {task['subject']} ({start_time}-{end_time})",
            due_date=task['date'],
            is_completed=task['is_completed']  # Set completion status
        )
        db.session.add(new_task)

        # Debug: Print added task
        print(f"Added Task: {new_task.title}, Due Date: {new_task.due_date}")

    db.session.commit()
    flash('Study plan tasks have been added to your home page.', 'success')
    return redirect(url_for('home'))

@app.route('/save_selections', methods=['POST'])
def save_selections():
    if 'user_id' not in session:
        flash('Please login to save your selections.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Debug: Print form data
    print(f"Form Data: {request.form}")

    # Clear previous selections
    SelectedSubject.query.filter_by(user_id=user_id).delete()
    CompletedModule.query.filter_by(user_id=user_id).delete()
    ExamDate.query.filter_by(user_id=user_id).delete()

    # Get selected subjects
    selected_subject_ids = []
    for i in range(1, 6):  # Assuming 5 subject slots as in your HTML
        subject_id = request.form.get(f'subject{i}')
        if subject_id and subject_id != "":
            selected_subject_ids.append(int(subject_id))
            selected_subject = SelectedSubject(
                user_id=user_id,
                subject_id=int(subject_id))
            db.session.add(selected_subject)

            # Save selected modules for this subject
            for j in range(1, 6):  # Assuming 5 modules per subject
                if request.form.get(f'module{i}_{j}') == '1':
                    module = Module.query.filter_by(subject_id=subject_id, name=f"Module {j}").first()
                    if module:
                        completed_module = CompletedModule(
                            user_id=user_id,
                            module_id=module.id)
                        db.session.add(completed_module)

    # Debug: Print selected subject IDs
    print(f"Selected Subject IDs: {selected_subject_ids}")

    # Process exam dates for each selected subject
    for i, subject_id in enumerate(selected_subject_ids, 1):
        exam_date_str = request.form.get(f'examDate{i}')
        if exam_date_str:
            try:
                exam_date_obj = datetime.strptime(exam_date_str, '%Y-%m-%d').date()

                # Add new exam date
                exam_date = ExamDate(
                    user_id=user_id,
                    subject_id=subject_id,
                    exam_date=exam_date_obj,
                    description=f"Exam for {Subject.query.get(subject_id).name}")
                db.session.add(exam_date)

                # Debug: Print exam date
                print(f"Exam Date for Subject {subject_id}: {exam_date_obj}")

            except ValueError:
                flash(f'Invalid date format for subject {i}. Please use YYYY-MM-DD.', 'error')

    db.session.commit()
    flash('Selections saved successfully!', 'success')
    return redirect(url_for('study_plan'))

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        flash('Please login to access the admin dashboard.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user or not user.is_admin:
        flash('You do not have permission to access the admin dashboard.', 'error')
        return redirect(url_for('home'))

    # Fetch all users, subjects, and other relevant data
    users = User.query.all()
    subjects = Subject.query.all()
    selected_subjects = SelectedSubject.query.all()
    exam_dates = ExamDate.query.all()
    tasks = Task.query.all()

    return render_template(
        'admin_dashboard.html',
        users=users,
        subjects=subjects,
        selected_subjects=selected_subjects,
        exam_dates=exam_dates,
        tasks=tasks
    )

# Route to add a new task
@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        flash('Please login to add a task.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')

    try:
        # Try parsing the date in the correct format (YYYY-MM-DD)
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                # If the format is incorrect, try parsing it in DD-MM-YYYY format
                try:
                    due_date = datetime.strptime(due_date_str, '%d-%m-%Y').date()
                except ValueError:
                    flash('Invalid date format. Please use YYYY-MM-DD or DD-MM-YYYY.', 'error')
                    return redirect(url_for('todo'))

        # Add the task to the database
        new_task = Task(
            user_id=user_id,
            title=title,
            description=description,
            due_date=due_date
        )
        db.session.add(new_task)
        db.session.commit()
        flash('Task added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while adding the task.', 'error')
        print(f"Error: {e}")

    return redirect(url_for('todo'))

# Route to mark a task as completed
@app.route('/complete_task/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    if 'user_id' not in session:
        flash('Please login to complete a task.', 'error')
        return redirect(url_for('login'))

    task = Task.query.get(task_id)
    if task and task.user_id == session['user_id']:
        task.is_completed = True
        task.date_completed = datetime.utcnow()

        # Calculate completion time
        completion_time = task.date_completed.time()
        if task.due_date and task.due_date < datetime.utcnow().date():
            flash('Task completed after the deadline!', 'warning')
        else:
            flash('Task marked as completed!', 'success')

        # Adjust future tasks using RL (only for study plan tasks)
        if task.title.startswith("Study"):
            user = User.query.get(session['user_id'])
            selected_subjects = SelectedSubject.query.filter_by(user_id=user.id).all()
            exam_dates = ExamDate.query.filter_by(user_id=user.id).all()

            # Only train the RL agent if exam_dates are available
            if exam_dates:
                subjects = [selected_subject.subject for selected_subject in selected_subjects]
                agent = train_rl_agent(user, subjects, exam_dates)

        db.session.commit()
    else:
        flash('Task not found or you do not have permission.', 'error')

    return redirect(url_for('home'))

# Route to delete a task
@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    if 'user_id' not in session:
        flash('Please login to delete a task.', 'error')
        return redirect(url_for('login'))

    task = Task.query.get(task_id)
    if task and task.user_id == session['user_id']:
        db.session.delete(task)
        db.session.commit()
        flash('Task deleted successfully!', 'success')
    else:
        flash('Task not found or you do not have permission.', 'error')

    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    init_db()  # Initialize database
    app.run(debug=True)