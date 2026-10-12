from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    security_question = db.Column(db.String(250), nullable=False)
    security_answer = db.Column(db.String(150), nullable=False)
    
    # Relationship to tasks
    tasks = db.relationship('Task', backref='owner', lazy=True, cascade="all, delete-orphan")

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    is_priority = db.Column(db.Boolean, default=False) # For "Today's Focus"
    start_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.Date, nullable=True) # If None, it's an indefinite daily task
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship to daily logs
    logs = db.relationship('DailyLog', backref='task', lazy=True, cascade="all, delete-orphan")

class DailyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    is_completed = db.Column(db.Boolean, default=False)