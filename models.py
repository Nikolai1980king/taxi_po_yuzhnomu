from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
import enum

db = SQLAlchemy()


class UserRole(enum.Enum):
    DRIVER = "driver"
    PASSENGER = "passenger"


class OrderStatus(enum.Enum):
    PENDING = "pending"  # Ожидает водителя
    ASSIGNED = "assigned"  # Назначен водителю, ждет подтверждения
    ACCEPTED = "accepted"  # Принят водителем
    IN_PROGRESS = "in_progress"  # В пути
    COMPLETED = "completed"  # Завершен
    CANCELLED = "cancelled"  # Отменен


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    role = db.Column(Enum(UserRole), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Для водителей
    is_online = db.Column(db.Boolean, default=False)
    queue_position = db.Column(db.Integer, nullable=True)  # Позиция в очереди
    current_order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    
    # Для пассажиров
    orders = db.relationship('Order', backref='passenger', lazy=True, foreign_keys='Order.passenger_id')
    
    def __repr__(self):
        return f'<User {self.username} ({self.role.value})>'


class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    passenger_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    pickup_address = db.Column(db.String(200), nullable=False)
    destination_address = db.Column(db.String(200), nullable=False)
    pickup_lat = db.Column(db.Float, nullable=True)
    pickup_lng = db.Column(db.Float, nullable=True)
    destination_lat = db.Column(db.Float, nullable=True)
    destination_lng = db.Column(db.Float, nullable=True)
    
    status = db.Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    assigned_at = db.Column(db.DateTime, nullable=True)  # Когда заказ был назначен водителю
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    price = db.Column(db.Float, nullable=True)
    
    def __repr__(self):
        return f'<Order {self.id} - {self.status.value}>'
