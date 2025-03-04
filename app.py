from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import numpy as np
import random
from collections import defaultdict
from flask_migrate import Migrate
from flask import jsonify
import speech_recognition as sr  # Import the SpeechRecognition library
import dateparser  # Import the dateparser library
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_session import Session

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this for production security

# PostgreSQL Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgre20@localhost/spark'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# SQLAlchemy Session Configuration
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY'] = db  # Use the existing SQLAlchemy instance
# Initialize Flask-Session
Session(app)

migrate = Migrate(app, db)

# Initialize Flask-Admin
admin = Admin(app, name='Admin Dashboard', template_mode='bootstrap3')

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
    total_reward = db.Column(db.Integer, default=0)  # Ensure default value is 0

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

# Add models to Flask-Admin
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Subject, db.session))
admin.add_view(ModelView(Module, db.session))
admin.add_view(ModelView(SelectedSubject, db.session))
admin.add_view(ModelView(CompletedModule, db.session))
admin.add_view(ModelView(ExamDate, db.session))
admin.add_view(ModelView(Task, db.session))

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
import numpy as np
import random
from collections import defaultdict

class QLearningAgent:
    def __init__(self, state_size, action_size, subjects, exam_dates):
        self.state_size = state_size
        self.action_size = action_size
        self.q_table = defaultdict(lambda: np.zeros(action_size))
        self.learning_rate = 0.1
        self.discount_factor = 0.99
        self.epsilon = 1.0
        self.epsilon_decay = 0.995
        self.epsilon_min = 0.01
        self.subjects = subjects
        self.exam_dates = exam_dates

    def get_action(self, state):
        """Get the recommended action from the RL agent."""
        if np.random.rand() <= self.epsilon:
            action = random.randrange(self.action_size)
            print(f"Random action selected: {action}")  # Debug statement
        else:
            action = np.argmax(self.q_table[tuple(state)])
            print(f"Optimal action selected: {action}")  # Debug statement
    
        return action

    def update_q_table(self, state, action, reward, next_state, done):
        state = tuple(state)
        next_state = tuple(next_state)
        q_value = self.q_table[state][action]
        next_q_value = np.max(self.q_table[next_state])
        new_q_value = q_value + self.learning_rate * (reward + self.discount_factor * next_q_value - q_value)
        self.q_table[state][action] = new_q_value
        if done:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def to_dict(self):
        """
    Serialize the RL agent to a dictionary.
    """
        # Serialize q_table keys as strings in a consistent format
        q_table_serialized = {str(tuple(map(int, k))): v.tolist() for k, v in self.q_table.items()}
        return {
            'state_size': self.state_size,
            'action_size': self.action_size,
            'q_table': q_table_serialized,
            'learning_rate': self.learning_rate,
            'discount_factor': self.discount_factor,
            'epsilon': self.epsilon,
            'epsilon_decay': self.epsilon_decay,
            'epsilon_min': self.epsilon_min,
            'subjects': [subject.id for subject in self.subjects],
            'exam_dates': [exam_date.id for exam_date in self.exam_dates]
        }

    @classmethod
    def from_dict(cls, data, subjects, exam_dates):
        """Deserialize the RL agent from a dictionary."""
        agent = cls(data['state_size'], data['action_size'], subjects, exam_dates)
    
        try:
            # Deserialize the q_table
            agent.q_table = defaultdict(
                lambda: np.zeros(data['action_size']),
                {tuple(map(int, k.strip('()').split(','))): np.array(v) 
                 for k, v in data['q_table'].items()}
                )
            agent.learning_rate = data['learning_rate']
            agent.discount_factor = data['discount_factor']
            agent.epsilon = data['epsilon']
            agent.epsilon_decay = data['epsilon_decay']
            agent.epsilon_min = data['epsilon_min']
        except Exception as e:
            print(f"Error deserializing RL agent: {e}")
            raise ValueError("Failed to deserialize RL agent data.")
    
        return agent
    
# Train the RL Agent
def train_rl_agent(user, subjects, exam_dates, episodes=1000):
    env = StudyScheduleEnv(user, subjects, exam_dates)
    agent = QLearningAgent(env.state_size, env.action_size, subjects, exam_dates)  # Pass subjects and exam_dates

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

def adjust_study_plan_based_on_rl(user, agent):
    """
    Adjust the study plan based on the RL agent's recommendations.
    """
    print("Adjusting study plan based on RL agent...")  # Debug statement

    # Get the user's study plan tasks
    study_plan_tasks = Task.query.filter(
        Task.user_id == user.id,
        Task.title.like("Study%")
    ).all()

    if not study_plan_tasks:
        print("No study plan tasks found. Skipping RL adjustments.")  # Debug statement
        return

    # Debugging: Print the tasks found
    print(f"Found {len(study_plan_tasks)} study plan tasks:")
    for task in study_plan_tasks:
        print(f"- {task.title} (Due: {task.due_date})")

    # Get the current state of the environment
    env = StudyScheduleEnv(user, agent.subjects, agent.exam_dates)
    state = env.reset()

    # Adjust tasks based on the RL agent's recommendations
    for task in study_plan_tasks:
        if not task.is_completed:
            # Get the recommended action from the RL agent
            action = agent.get_action(state)
            print(f"Recommended action for task {task.title}: {action}")  # Debug statement

            # Update the task's due date based on the action
            try:
                module = env.modules[action]
                safe_due_date = datetime.utcnow().date() + timedelta(days=env.days_remaining - 2)

                # Prevent due dates from being in the past
                if safe_due_date < datetime.utcnow().date():
                    safe_due_date = datetime.utcnow().date()  # Set it to today if it's in the past

                task.due_date = safe_due_date
                print(f"Updated due date for task {task.title} to {task.due_date}")  # Debug statement
            except IndexError:
                print(f"Invalid action {action} for task {task.title}. Skipping update.")  # Debug statement
                continue

            # Update the state
            next_state, _, _ = env.step(action)
            state = next_state

    # Commit changes to the database
    db.session.commit()
    print("Study plan adjusted based on RL agent.")  # Debug statement

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
    user = User.query.get(user_id)  # Fetch the user from the database
    if not user:
        session.clear()
        flash('User not found. Please login again.', 'error')
        return redirect(url_for('login'))

    # Get all tasks (including study plan tasks)
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.due_date.asc()).all()

    # Get study plan tasks (filter by tasks with titles starting with "Study")
    study_plan_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.title.like("Study%")  # Filter tasks with titles starting with "Study"
    ).order_by(Task.due_date.asc()).all()

    return render_template(
        'home.html',
        username=user.username,
        user=user,  # Pass the user object to the template
        tasks=tasks,
        study_plan_tasks=study_plan_tasks
    )

@app.route('/study_plan')
def study_plan():
    """
    Generate or update the study plan for the logged-in user.
    If an RL agent is available in the session, it will be used to adjust the study plan.
    Otherwise, a default study plan will be generated.
    """
    # Check if the user is logged in
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

    if not selected_subjects or not exam_dates:
        flash('Please select subjects and exam dates first.', 'error')
        return redirect(url_for('exam_dashboard'))

    # Clear existing study plan tasks
    try:
        clear_study_plan_tasks(user_id)
    except Exception as e:
        flash('An error occurred while clearing the study plan. Please try again.', 'error')
        return redirect(url_for('home'))

    # Debugging: Print selected subjects, exam dates, and RL agent data
    print("Selected Subjects:", selected_subjects)
    print("Exam Dates:", exam_dates)
    print("RL Agent Data in Session:", session.get('rl_agent'))

    # Generate the default study plan first
    generate_default_study_plan(user, selected_subjects, exam_dates)

    # Recreate the RL agent from the session data (if available)
    if 'rl_agent' in session:
        agent_data = session['rl_agent']
        required_fields = ['state_size', 'action_size', 'q_table', 'learning_rate', 'discount_factor', 'epsilon', 'epsilon_decay', 'epsilon_min', 'subjects', 'exam_dates']
        
        # Validate session data
        if not all(field in agent_data for field in required_fields):
            print("Invalid RL agent data in session.")
            flash('Invalid RL agent data. Generating a default study plan.', 'warning')
        else:
            try:
                subjects = [Subject.query.get(subject_id) for subject_id in agent_data['subjects']]
                exam_dates = [ExamDate.query.get(exam_date_id) for exam_date_id in agent_data['exam_dates']]
                agent = QLearningAgent.from_dict(agent_data, subjects, exam_dates)
                adjust_study_plan_based_on_rl(user, agent)  # Use RL to adjust the study plan
            except Exception as e:
                print(f"Error recreating RL agent: {e}")
                flash('An error occurred while recreating the RL agent. Generating a default study plan.', 'warning')
    else:
        print("RL Agent not found in session.")  # Debug statement
        flash('RL agent not found. Generating a default study plan.', 'warning')

    db.session.commit()
    print("Tasks committed to the database.")  # Debug statement
    flash('Study plan tasks have been added to your home page.', 'success')
    return redirect(url_for('home'))

def clear_study_plan_tasks(user_id):
    """
    Helper function to clear existing study plan tasks for the user.
    """
    Task.query.filter(
        Task.user_id == user_id,
        Task.title.like("Study%")
    ).delete()
    db.session.commit()

def generate_default_study_plan(user, selected_subjects, exam_dates):
    """
    Helper function to generate a default study plan without duplicates.
    """
    print("Generating default study plan...")  # Debug statement
    study_schedule = []
    current_date = datetime.today().date()

    for selected_subject in selected_subjects:
        subject = Subject.query.get(selected_subject.subject_id)
        if subject:
            exam_date_record = next((ed for ed in exam_dates if ed.subject_id == subject.id), None)
            exam_date = exam_date_record.exam_date if exam_date_record else (current_date + timedelta(days=30))
            selected_modules = (
                db.session.query(Module)
                .join(CompletedModule, CompletedModule.module_id == Module.id)
                .filter(CompletedModule.user_id == user.id, Module.subject_id == subject.id)
                .all()
            )

            for module in selected_modules:
                # Ensure each module is only added once
                if module.name not in [task['module'] for task in study_schedule]:
                    days_before_exam = (exam_date - current_date).days
                    days_per_module = max(1, days_before_exam // len(selected_modules)) if selected_modules else 1
                    study_date = current_date + timedelta(days=len(study_schedule))
                    
                    # Ensure the study date is at least 2 days before the exam
                    if (exam_date - study_date).days < 2:
                        study_date = exam_date - timedelta(days=2)

                    study_schedule.append({
                        'date': study_date,
                        'module': module.name,
                        'subject': subject.name,
                        'subject_id': subject.id,
                        'is_completed': False
                    })
                    print(f"Added module {module.name} to study schedule on {study_date}")  # Debug statement

    # Sort the study schedule by date
    study_schedule.sort(key=lambda x: x['date'])

    # Create tasks for the study schedule
    for task in study_schedule:
        if user.person_type == 'morning':
            start_time = '08:00'
            end_time = '10:00'
        else:
            start_time = '20:00'
            end_time = '22:00'

        if user.learner_type == 'slow':
            adjusted_end_time = datetime.strptime(end_time, '%H:%M') + timedelta(hours=1)
            end_time = adjusted_end_time.strftime('%H:%M')

        new_task = Task(
            user_id=user.id,
            title=f"Study {task['subject']} - {task['module']}",
            description=f"Complete {task['module']} for {task['subject']} ({start_time}-{end_time})",
            due_date=task['date'],
            is_completed=task['is_completed']
        )
        db.session.add(new_task)
        print(f"Created task: {new_task.title} due on {new_task.due_date}")  # Debug statement

    # Commit changes to the database
    db.session.commit()
    print("Default study plan generated and tasks added to the database.")  # Debug statement

@app.route('/save_selections', methods=['POST'])
def save_selections():
    """
    Save the user's selected subjects, modules, and exam dates.
    Train the RL agent after saving the selections.
    """
    if 'user_id' not in session:
        flash('Please login to save your selections.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Clear previous selections
    try:
        SelectedSubject.query.filter_by(user_id=user_id).delete()
        CompletedModule.query.filter_by(user_id=user_id).delete()
        ExamDate.query.filter_by(user_id=user_id).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while clearing previous selections. Please try again.', 'error')
        return redirect(url_for('exam_dashboard'))

    # Get selected subjects
    selected_subject_ids = []
    for i in range(1, 6):  # Assuming 5 subject slots
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

    # Process exam dates for each selected subject
    for i, subject_id in enumerate(selected_subject_ids, 1):
        exam_date_str = request.form.get(f'examDate{i}')
        if exam_date_str:
            try:
                exam_date_obj = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
                exam_date = ExamDate(
                    user_id=user_id,
                    subject_id=subject_id,
                    exam_date=exam_date_obj,
                    description=f"Exam for {Subject.query.get(subject_id).name}")
                db.session.add(exam_date)
            except ValueError:
                flash(f'Invalid date format for subject {i}. Please use YYYY-MM-DD.', 'error')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while saving your selections. Please try again.', 'error')
        return redirect(url_for('exam_dashboard'))

    # Train the RL agent after saving selections
    user = User.query.get(user_id)
    selected_subjects = SelectedSubject.query.filter_by(user_id=user_id).all()
    subjects = [Subject.query.get(s.subject_id) for s in selected_subjects]
    exam_dates = ExamDate.query.filter_by(user_id=user_id).all()

    # Train the RL agent
    agent = train_rl_agent(user, subjects, exam_dates, episodes=1000)

    # Store the serialized agent in the session
    session['rl_agent'] = agent.to_dict()
    print("RL Agent stored in session:", session['rl_agent'])

    flash('Selections saved successfully!', 'success')
    return redirect(url_for('study_plan'))

@app.route('/retrain_rl_agent', methods=['POST'])
def retrain_rl_agent():
    """
    Retrain the RL agent based on the user's current selections.
    """
    if 'user_id' not in session:
        flash('Please login to retrain the RL agent.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    selected_subjects = SelectedSubject.query.filter_by(user_id=user_id).all()
    subjects = [Subject.query.get(s.subject_id) for s in selected_subjects]
    exam_dates = ExamDate.query.filter_by(user_id=user_id).all()

    # Retrain the RL agent
    agent = train_rl_agent(user, subjects, exam_dates, episodes=1000)

    # Store the retrained agent in the session
    session['rl_agent'] = agent.to_dict()
    flash('RL agent retrained successfully!', 'success')
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

# Add New Subject
@app.route('/add_subject', methods=['POST'])
def add_subject():
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('admin_dashboard'))

    name = request.form['name']
    semester = int(request.form['semester'])
    code = request.form.get('code', None)

    new_subject = Subject(name=name, semester=semester, code=code)
    db.session.add(new_subject)
    db.session.commit()
    flash('Subject added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# Edit Subject
@app.route('/edit_subject/<int:subject_id>', methods=['GET', 'POST'])
def edit_subject(subject_id):
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('admin_dashboard'))

    subject = Subject.query.get_or_404(subject_id)
    if request.method == 'POST':
        subject.name = request.form['name']
        subject.semester = int(request.form['semester'])
        subject.code = request.form.get('code', None)
        db.session.commit()
        flash('Subject updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_subject.html', subject=subject)

# Delete Subject
@app.route('/delete_subject/<int:subject_id>', methods=['POST'])
def delete_subject(subject_id):
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('admin_dashboard'))

    subject = Subject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

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
        return jsonify({'error': 'Please login to complete a task.'}), 401

    task = Task.query.get(task_id)
    if task and task.user_id == session['user_id']:
        user = User.query.get(session['user_id'])

        # Initialize total_reward to 0 if it's None
        if user.total_reward is None:
            user.total_reward = 0

        # Mark task as completed
        task.is_completed = True
        task.date_completed = datetime.utcnow()

        # Calculate reward
        if task.due_date and task.due_date < datetime.utcnow().date():
            reward = -10  # Penalty for completing after the deadline
            message = 'Task completed after the deadline!'
        else:
            reward = 20  # Reward for completing on time
            message = 'Task marked as completed!'

        # Update user's total reward
        user.total_reward += reward
        db.session.commit()

        # Return JSON response
        return jsonify({
            'success': True,
            'message': message,
            'total_reward': user.total_reward
        })
    else:
        return jsonify({'error': 'Task not found or you do not have permission.'}), 404
    
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

# New route to handle speech input
@app.route('/speech_to_text', methods=['POST'])
def speech_to_text():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login to add a task.'}), 401

    try:
        # Get the spoken text from the request
        data = request.get_json()
        spoken_text = data.get('text')

        if not spoken_text:
            return jsonify({'error': 'No text provided.'}), 400

        print(f"You said: {spoken_text}")

        # Extract task details from the spoken text
        if "add task" in spoken_text.lower():
            # Split the spoken text into parts
            parts = spoken_text.lower().split("add task")[1].split("due")
            title = parts[0].strip()  # Task title is always the first part
            due_date = None

            # Check if a due date was provided
            if len(parts) > 1:
                due_date_str = parts[1].strip()

                # Use dateparser to parse natural language dates
                due_date = dateparser.parse(due_date_str)

                if not due_date:
                    # If dateparser couldn't parse the date, log a message and proceed without a due date
                    print("Could not parse the due date. Proceeding without a due date.")
                else:
                    # Convert the parsed date to a date object (without time)
                    due_date = due_date.date()

            # Add the task to the database
            new_task = Task(
                user_id=session['user_id'],
                title=title,
                description=f"Task added via speech: {title}",
                due_date=due_date
            )
            db.session.add(new_task)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Task added successfully via speech!',
                'task': {
                    'id': new_task.id,
                    'title': new_task.title,
                    'description': new_task.description,
                    'due_date': new_task.due_date.strftime('%Y-%m-%d') if new_task.due_date else None
                }
            })
        else:
            return jsonify({'error': 'Could not understand the task. Please try again.'}), 400

    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500
    
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    init_db()  # Initialize database
    app.run(debug=True)