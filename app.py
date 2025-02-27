from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

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

    # Generate the study plan
    study_plan = []
    for exam in exam_dates:
        subject = Subject.query.get(exam.subject_id)
        modules = Module.query.filter_by(subject_id=exam.subject_id).all()

        # Calculate the number of days available for study
        days_available = (exam.exam_date - datetime.today().date()).days
        if days_available <= 0:
            flash(f'Exam for {subject.name} is overdue or today!', 'error')
            continue

        # Adjust workload based on learner type
        modules_per_day = len(modules) // days_available
        if user.learner_type == 'slow':
            modules_per_day = max(1, modules_per_day - 1)  # Reduce workload for slow learners
        elif user.learner_type == 'fast':
            modules_per_day = min(modules_per_day + 1, len(modules))  # Increase workload for fast learners

        # Assign modules to days
        study_days = []
        for day in range(days_available):
            start_index = day * modules_per_day
            end_index = start_index + modules_per_day
            modules_for_day = modules[start_index:end_index]
            study_days.append({
                'date': (datetime.today() + timedelta(days=day)).date(),
                'modules': [module.name for module in modules_for_day]
            })

        study_plan.append({
            'subject': subject.name,
            'exam_date': exam.exam_date,
            'study_days': study_days
        })

    return render_template(
        'study_plan.html',
        username=user.username,
        study_plan=study_plan
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

    # Get tasks (including study plan tasks)
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.due_date.asc()).all()

    return render_template(
        'home.html',
        username=user.username,
        tasks=tasks
    )

@app.route('/save_selections', methods=['POST'])
def save_selections():
    if 'user_id' not in session:
        flash('Please login to save your selections.', 'error')
        return redirect(url_for('login'))
   
    user_id = session['user_id']
   
    # Clear previous selections
    SelectedSubject.query.filter_by(user_id=user_id).delete()
   
    # Get selected subjects
    for i in range(1, 6):  # Assuming 5 subject slots as in your HTML
        subject_id = request.form.get(f'subject{i}')
        if subject_id and subject_id != "":
            selected_subject = SelectedSubject(
                user_id=user_id,
                subject_id=int(subject_id)
            )
            db.session.add(selected_subject)
   
    # Get completed modules
    CompletedModule.query.filter_by(user_id=user_id).delete()
    for key, value in request.form.items():
        if key.startswith('module') and '_' in key:
            parts = key.split('_')
            subject_index = int(parts[0].replace('module', ''))
            module_index = int(parts[1])
           
            subject_id = request.form.get(f'subject{subject_index}')
            if subject_id and subject_id != "":
                # Find the module in the database
                subject = Subject.query.get(int(subject_id))
                if subject:
                    module = Module.query.filter_by(
                        subject_id=subject.id,
                        name=f"Module {module_index}"
                    ).first()
                   
                    if module:
                        completed_module = CompletedModule(
                            user_id=user_id,
                            module_id=module.id
                        )
                        db.session.add(completed_module)
   
    # Save exam date if provided
    exam_date_str = request.form.get('examDate')
    if exam_date_str:
        try:
            exam_date_obj = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
           
            # Get the subject ID (assuming it's for the first selected subject)
            subject_id = request.form.get('subject1')
            if subject_id and subject_id != "":
                # Delete existing exam date for this subject
                ExamDate.query.filter_by(
                    user_id=user_id,
                    subject_id=int(subject_id)
                ).delete()
               
                # Add new exam date
                exam_date = ExamDate(
                    user_id=user_id,
                    subject_id=int(subject_id),
                    exam_date=exam_date_obj,
                    description=f"Exam for {Subject.query.get(int(subject_id)).name}"
                )
                db.session.add(exam_date)
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
   
    db.session.commit()
    flash('Your selections have been saved.', 'success')
    return redirect(url_for('home'))

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin', False):
        flash('You do not have permission to access the admin dashboard.', 'error')
        return redirect(url_for('login'))
   
    users = User.query.filter_by(is_admin=False).all()
    subjects = Subject.query.all()
   
    return render_template(
        'admin_dashboard.html',
        username=session['username'],
        users=users,
        subjects=subjects
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
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
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
        db.session.commit()
        flash('Task marked as completed!', 'success')
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