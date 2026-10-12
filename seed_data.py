from app import app, bcrypt
from models import db, User, Task, DailyLog
from datetime import date, timedelta
import random

# --- CONFIGURATION ---
DAYS_OF_HISTORY = 90  # Change this to 180 or 365 for even more data
# ---------------------

with app.app_context():
    # 1. Create the Demo User
    username = 'demo'
    password = 'demo'
    user = User.query.filter_by(username=username).first()
    
    if not user:
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, password_hash=hashed_pw, security_question='test', security_answer='test')
        db.session.add(user)
        db.session.commit()
    
    # 2. Wipe existing tasks for demo user to ensure a clean slate
    old_tasks = Task.query.filter_by(user_id=user.id).all()
    for task in old_tasks:
        db.session.delete(task)
    db.session.commit()

    # 3. Create realistic tasks with targeted consistency rates
    today = date.today()
    start_date = today - timedelta(days=DAYS_OF_HISTORY)
    
    tasks_data = [
        {"title": "Read 20 pages", "priority": True, "weight": 0.85},   # Strong
        {"title": "Drink 2L Water", "priority": False, "weight": 0.90}, # Strong
        {"title": "Meditate", "priority": False, "weight": 0.65},       # Average
        {"title": "No Social Media", "priority": False, "weight": 0.35} # Weak
    ]
    
    tasks = []
    for t in tasks_data:
        task = Task(title=t['title'], is_priority=t['priority'], start_date=start_date, user_id=user.id)
        db.session.add(task)
        tasks.append((task, t['weight']))
    
    db.session.commit()

    # 4. Simulate history based on the configured days
    for i in range(DAYS_OF_HISTORY + 1): 
        current_date = start_date + timedelta(days=i)
        for task, weight in tasks:
            # Randomly mark as completed based on the task's assigned weight
            if random.random() < weight:
                log = DailyLog(task_id=task.id, date=current_date, is_completed=True)
                db.session.add(log)
                
    db.session.commit()
    print(f"Demo account successfully seeded with {DAYS_OF_HISTORY} days of history! Login with Username: 'demo', Password: 'demo'")