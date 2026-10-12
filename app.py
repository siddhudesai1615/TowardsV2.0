from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from models import db, User, Task, DailyLog
from datetime import datetime, date, timedelta
import random
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from collections import Counter
import os

app = Flask(__name__)
# Security key for session cookies
app.config['SECRET_KEY'] = 'towards_v2_super_secret_key'
# Setting up the SQLite database file
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create the database tables before the first request
with app.app_context():
    db.create_all()

# --- ROUTES ---

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        question = request.form.get('sec_question').strip()
        answer = request.form.get('sec_answer').strip().lower() # Lowercase for easier matching later

        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.', 'error')
            return redirect(url_for('register'))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password_hash=hashed_pw, security_question=question, security_answer=answer)
        
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check username and password.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    quotes = [
        "Small daily improvements are the key to staggering long-term results.",
        "Consistency is what transforms average into excellence.",
        "Focus on the step in front of you, not the whole staircase.",
        "Action is the foundational key to all success."
    ]
    quote = random.choice(quotes)
    
    # Fetch tasks that are marked active
    all_active_tasks = Task.query.filter_by(user_id=current_user.id, is_active=True).all()
    today = date.today()
    
    tasks = []
    for task in all_active_tasks:
        # BUG FIX 1 & 2: Auto-archive expired tasks so they leave the dashboard 
        # but keep their history for the Analytics page.
        if task.end_date and task.end_date < today:
            task.is_active = False
            db.session.commit()
            continue
            
        tasks.append(task)
    
    completed_count = 0
    total_possible_days = 0
    total_completed_days = 0

    for task in tasks:
        log = DailyLog.query.filter_by(task_id=task.id, date=today).first()
        task.completed_today = log.is_completed if log else False
        
        if task.completed_today:
            completed_count += 1
            
        # Calculate Streak
        streak = 0
        check_date = today
        if not task.completed_today:
            check_date -= timedelta(days=1)
            
        while True:
            past_log = DailyLog.query.filter_by(task_id=task.id, date=check_date).first()
            if past_log and past_log.is_completed:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        task.streak = streak
        
        # Dashboard top stat calculations
        days_since_start = (today - task.start_date).days + 1
        if days_since_start > 0:
            completed_logs = DailyLog.query.filter_by(task_id=task.id, is_completed=True).count()
            total_possible_days += days_since_start
            total_completed_days += completed_logs

    remaining_count = len(tasks) - completed_count
    avg_consistency = int((total_completed_days / total_possible_days) * 100) if total_possible_days > 0 else 0
        
    return render_template('dashboard.html', 
                           quote=quote, 
                           tasks=tasks, 
                           completed=completed_count, 
                           remaining=remaining_count, 
                           avg_consistency=avg_consistency)


@app.route('/toggle_task/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Security: Only the owner can check off this task
    if task.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
    today = date.today()
    log = DailyLog.query.filter_by(task_id=task.id, date=today).first()
    
    if log:
        # Toggle existing log
        log.is_completed = not log.is_completed
    else:
        # Create a new log for today marked as completed
        log = DailyLog(task_id=task.id, date=today, is_completed=True)
        db.session.add(log)
        
    db.session.commit()
    return jsonify({'status': 'success', 'is_completed': log.is_completed})

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    title = request.form.get('title').strip()
    end_date_str = request.form.get('end_date')
    is_priority = True if request.form.get('is_priority') else False
    
    # Convert HTML date string to Python Date object if provided
    end_date = None
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
    new_task = Task(title=title, is_priority=is_priority, end_date=end_date, user_id=current_user.id)
    db.session.add(new_task)
    db.session.commit()
    
    return redirect(url_for('dashboard'))

@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    # Security check: Ensure the user owns the task before deleting
    if task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    # Stage 1: Find the user and their question
    if request.method == 'POST':
        username = request.form.get('username').strip()
        user = User.query.filter_by(username=username).first()
        
        if user:
            return render_template('forgot_password.html', step=2, username=user.username, question=user.security_question)
        else:
            flash('Username not found.', 'error')
            return redirect(url_for('forgot_password'))
            
    return render_template('forgot_password.html', step=1)

@app.route('/reset_password', methods=['POST'])
def reset_password():
    # Stage 2: Verify answer and update password
    username = request.form.get('username')
    answer = request.form.get('sec_answer').strip().lower()
    new_password = request.form.get('new_password')
    
    user = User.query.filter_by(username=username).first()
    
    if user and user.security_answer == answer:
        hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')
        user.password_hash = hashed_pw
        db.session.commit()
        flash('Password reset successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    else:
        flash('Incorrect security answer.', 'error')
        # Send them back to stage 2 to try again
        return render_template('forgot_password.html', step=2, username=user.username, question=user.security_question)


@app.route('/analytics')
@login_required
def analytics():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    today = date.today()
    
    if not tasks:
        flash("Add some tasks to see analytics!", "info")
        return redirect(url_for('dashboard'))
        
    earliest_task = min(tasks, key=lambda t: t.start_date)
    start_date_all = earliest_task.start_date
    days_total = (today - start_date_all).days + 1
    
    task_stats, strong_points, weak_points = [], [], []
    tot_poss_all = tot_comp_all = tot_poss_week = tot_comp_week = tot_poss_month = tot_comp_month = 0
    
    task_ids = [t.id for t in tasks]
    all_logs = DailyLog.query.filter(DailyLog.task_id.in_(task_ids), DailyLog.is_completed==True).all()
    
    # For the line charts: Count total tasks completed per day across all habits
    log_dates = [log.date for log in all_logs]
    date_counts = Counter(log_dates)
    
    labels_7 = [(today - timedelta(days=i)).strftime('%b %d') for i in range(6, -1, -1)]
    data_7 = [date_counts[today - timedelta(days=i)] for i in range(6, -1, -1)]
    
    labels_30 = [(today - timedelta(days=i)).strftime('%b %d') for i in range(29, -1, -1)]
    data_30 = [date_counts[today - timedelta(days=i)] for i in range(29, -1, -1)]
    
    labels_all = [(today - timedelta(days=i)).strftime('%b %d') for i in range(days_total-1, -1, -1)]
    data_all = [date_counts[today - timedelta(days=i)] for i in range(days_total-1, -1, -1)]

    for task in tasks:
        days_active = (today - task.start_date).days + 1
        if days_active <= 0: continue
            
        # THE FIX: Filter the pre-fetched logs strictly for this specific task
        task_logs = [log.date for log in all_logs if log.task_id == task.id]
        
        comp_all = len(task_logs)
        cons_all = int((comp_all / days_active) * 100)
        comp_week = sum(1 for d in task_logs if d >= today - timedelta(days=6))
        cons_week = int((comp_week / min(7, days_active)) * 100) if min(7, days_active) > 0 else 0
        comp_month = sum(1 for d in task_logs if d >= today - timedelta(days=29))
        cons_month = int((comp_month / min(30, days_active)) * 100) if min(30, days_active) > 0 else 0
        
        task_stats.append({'title': task.title, 'consistency': cons_all, 'cons_week': cons_week, 'cons_month': cons_month, 'cons_all': cons_all})
        
        if cons_all >= 80: strong_points.append(task.title)
        elif cons_all < 50: weak_points.append(task.title)
            
        tot_poss_all += days_active; tot_comp_all += comp_all
        tot_poss_week += min(7, days_active); tot_comp_week += comp_week
        tot_poss_month += min(30, days_active); tot_comp_month += comp_month
        
    return render_template('analytics.html', 
                           task_stats=task_stats, strong_points=strong_points, weak_points=weak_points,
                           overall_all=int((tot_comp_all/tot_poss_all)*100) if tot_poss_all > 0 else 0,
                           overall_week=int((tot_comp_week/tot_poss_week)*100) if tot_poss_week > 0 else 0,
                           overall_month=int((tot_comp_month/tot_poss_month)*100) if tot_poss_month > 0 else 0,
                           labels_7=labels_7, data_7=data_7, labels_30=labels_30, data_30=data_30, 
                           labels_all=labels_all, data_all=data_all, total_tasks=len(tasks))


@app.route('/reset_account', methods=['POST'])
@login_required
def reset_account():
    # Fetch all tasks owned by the current user
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    # Deleting the task automatically deletes its DailyLogs 
    # because we set cascade="all, delete-orphan" in models.py
    for task in tasks:
        db.session.delete(task)
        
    db.session.commit()
    flash('Your account history has been wiped. Enjoy your fresh start!', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)