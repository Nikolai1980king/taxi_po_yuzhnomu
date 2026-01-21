from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from config import Config
from models import db, User, Order, UserRole, OrderStatus
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальная очередь водителей (ID водителей в порядке очереди)
driver_queue = []
queue_lock = threading.Lock()

# Активные таймеры для заказов
order_timers = {}


def init_db():
    """Инициализация базы данных"""
    with app.app_context():
        db.create_all()


def add_driver_to_queue(driver_id):
    """Добавить водителя в очередь"""
    with queue_lock:
        if driver_id not in driver_queue:
            driver_queue.append(driver_id)
            # Обновить позицию в БД
            driver = User.query.get(driver_id)
            if driver:
                driver.queue_position = len(driver_queue)
                db.session.commit()
            socketio.emit('queue_updated', {'queue': driver_queue}, broadcast=True)


def remove_driver_from_queue(driver_id):
    """Удалить водителя из очереди"""
    with queue_lock:
        if driver_id in driver_queue:
            driver_queue.remove(driver_id)
            # Обновить позиции в БД
            update_queue_positions()
            socketio.emit('queue_updated', {'queue': driver_queue}, broadcast=True)


def update_queue_positions():
    """Обновить позиции водителей в очереди в БД"""
    for idx, driver_id in enumerate(driver_queue, 1):
        driver = User.query.get(driver_id)
        if driver:
            driver.queue_position = idx
    db.session.commit()


def rebuild_driver_queue():
    """Восстановить очередь водителей из БД (после перезапуска сервера)"""
    global driver_queue
    with app.app_context():
        with queue_lock:
            driver_queue.clear()
            drivers = User.query.filter(User.role == UserRole.DRIVER, User.is_online == True).all()
            drivers.sort(key=lambda u: (u.queue_position is None, u.queue_position or 0))
            for u in drivers:
                driver_queue.append(u.id)
            update_queue_positions()


def assign_order_to_next_driver(order_id):
    """Назначить заказ следующему водителю в очереди"""
    with queue_lock:
        if not driver_queue:
            return None
        
        order = Order.query.get(order_id)
        if not order or order.status != OrderStatus.PENDING:
            return None
        
        # Найти первого доступного водителя
        assigned_driver_id = None
        for driver_id in driver_queue:
            driver = User.query.get(driver_id)
            if driver and driver.is_online and driver.is_active and not driver.current_order_id:
                assigned_driver_id = driver_id
                break
        
        if assigned_driver_id:
            order.driver_id = assigned_driver_id
            order.status = OrderStatus.ASSIGNED
            order.assigned_at = datetime.utcnow()
            
            driver = User.query.get(assigned_driver_id)
            driver.current_order_id = order_id
            
            db.session.commit()
            
            # Уведомить водителя через WebSocket
            socketio.emit('new_order', {
                'order_id': order_id,
                'pickup_address': order.pickup_address,
                'destination_address': order.destination_address,
                'pickup_lat': order.pickup_lat,
                'pickup_lng': order.pickup_lng,
                'destination_lat': order.destination_lat,
                'destination_lng': order.destination_lng,
                'assigned_at': order.assigned_at.isoformat()
            }, room=f'driver_{assigned_driver_id}')
            
            # Уведомить пассажира
            socketio.emit('order_assigned', {
                'order_id': order_id,
                'driver_id': assigned_driver_id
            }, room=f'passenger_{order.passenger_id}')
            
            # Запустить таймер
            start_order_timer(order_id, assigned_driver_id)
            
            return assigned_driver_id
    
    return None


def start_order_timer(order_id, driver_id):
    """Запустить таймер для заказа (1 минута на принятие)"""
    def timer_callback():
        time.sleep(Config.ORDER_TIMEOUT_SECONDS)
        
        with app.app_context():
            order = Order.query.get(order_id)
            if order and order.status == OrderStatus.ASSIGNED and order.driver_id == driver_id:
                # Водитель не принял заказ, переходим к следующему
                driver = User.query.get(driver_id)
                if driver:
                    driver.current_order_id = None
                
                order.driver_id = None
                order.status = OrderStatus.PENDING
                order.assigned_at = None
                db.session.commit()
                
                # Уведомить водителя об отмене
                socketio.emit('order_timeout', {'order_id': order_id}, room=f'driver_{driver_id}')
                
                # Попробовать назначить следующему водителю
                assign_order_to_next_driver(order_id)
        
        # Удалить таймер
        if order_id in order_timers:
            del order_timers[order_id]
    
    timer_thread = threading.Thread(target=timer_callback, daemon=True)
    timer_thread.start()
    order_timers[order_id] = timer_thread


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/driver')
def driver_page():
    return render_template('driver.html', yandex_maps_api_key=app.config.get('YANDEX_MAPS_API_KEY', ''))


@app.route('/passenger')
def passenger_page():
    return render_template('passenger.html', yandex_maps_api_key=app.config.get('YANDEX_MAPS_API_KEY', ''))


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    phone = data.get('phone')
    role = data.get('role')
    
    if not username or not phone or not role:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(phone=phone).first():
        return jsonify({'error': 'Phone already exists'}), 400
    
    user = User(
        username=username,
        phone=phone,
        role=UserRole[role.upper()]
    )
    db.session.add(user)
    db.session.commit()
    
    session['user_id'] = user.id
    session['user_role'] = role
    
    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'role': user.role.value
    }), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    session['user_id'] = user.id
    session['user_role'] = user.role.value
    
    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'role': user.role.value,
        'is_online': user.is_online if user.role == UserRole.DRIVER else None
    }), 200


@app.route('/api/driver/online', methods=['POST'])
def driver_online():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user or user.role != UserRole.DRIVER:
        return jsonify({'error': 'Not a driver'}), 403
    
    user.is_online = True
    db.session.commit()
    
    add_driver_to_queue(user_id)
    
    # Обновить позицию после добавления в очередь
    user = User.query.get(user_id)
    
    return jsonify({'status': 'online', 'queue_position': user.queue_position}), 200


@app.route('/api/driver/offline', methods=['POST'])
def driver_offline():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user or user.role != UserRole.DRIVER:
        return jsonify({'error': 'Not a driver'}), 403
    
    user.is_online = False
    
    # Если есть текущий заказ, который еще не принят, вернуть его в очередь
    if user.current_order_id:
        order = Order.query.get(user.current_order_id)
        if order:
            if order.status == OrderStatus.ASSIGNED:
                # Остановить таймер
                if order.id in order_timers:
                    del order_timers[order.id]
                
                # Вернуть заказ в очередь
                order.status = OrderStatus.PENDING
                order.driver_id = None
                order.assigned_at = None
                
                # Попробовать назначить следующему водителю
                assign_order_to_next_driver(order.id)
            elif order.status == OrderStatus.ACCEPTED:
                # Если заказ принят, оставить его у водителя
                # Водитель может завершить заказ даже будучи офлайн
                pass
    
    db.session.commit()
    
    remove_driver_from_queue(user_id)
    
    return jsonify({'status': 'offline'}), 200


@app.route('/api/user/current', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'role': user.role.value,
        'is_online': user.is_online if user.role == UserRole.DRIVER else None,
        'queue_position': user.queue_position if user.role == UserRole.DRIVER else None
    }), 200


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'ok'}), 200


@app.route('/api/me/switch-role', methods=['POST'])
def switch_role():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.json or {}
    role = (data.get('role') or '').strip().lower()
    if role not in ('driver', 'passenger'):
        return jsonify({'error': 'Укажите роль: driver или passenger'}), 400
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    want = UserRole.DRIVER if role == 'driver' else UserRole.PASSENGER
    if user.role == want:
        session['user_role'] = user.role.value
        return jsonify({'role': user.role.value}), 200
    if want == UserRole.PASSENGER:
        if user.role == UserRole.DRIVER and user.current_order_id:
            return jsonify({'error': 'Завершите или отмените текущий заказ перед сменой роли'}), 400
        if user.role == UserRole.DRIVER:
            remove_driver_from_queue(user_id)
            user.is_online = False
        user.role = UserRole.PASSENGER
        session['user_role'] = 'passenger'
    else:
        user.role = UserRole.DRIVER
        session['user_role'] = 'driver'
    db.session.commit()
    return jsonify({'role': user.role.value}), 200


@app.route('/api/driver/orders/current', methods=['GET'])
def get_current_order():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user or user.role != UserRole.DRIVER:
        return jsonify({'error': 'Not a driver'}), 403
    
    if user.current_order_id:
        order = Order.query.get(user.current_order_id)
        if order:
            return jsonify({
                'order_id': order.id,
                'pickup_address': order.pickup_address,
                'destination_address': order.destination_address,
                'pickup_lat': order.pickup_lat,
                'pickup_lng': order.pickup_lng,
                'destination_lat': order.destination_lat,
                'destination_lng': order.destination_lng,
                'status': order.status.value,
                'assigned_at': order.assigned_at.isoformat() if order.assigned_at else None
            }), 200
    
    return jsonify({'order': None}), 200


@app.route('/api/driver/orders/<int:order_id>/accept', methods=['POST'])
def accept_order(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user or user.role != UserRole.DRIVER:
        return jsonify({'error': 'Not a driver'}), 403
    
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if order.driver_id != user_id:
        return jsonify({'error': 'Order not assigned to you'}), 403
    
    if order.status != OrderStatus.ASSIGNED:
        return jsonify({'error': 'Order cannot be accepted'}), 400
    
    # Остановить таймер
    if order_id in order_timers:
        del order_timers[order_id]
    
    order.status = OrderStatus.ACCEPTED
    # Водитель остается в очереди, но с текущим заказом
    db.session.commit()
    
    # Уведомить пассажира
    socketio.emit('order_accepted', {
        'order_id': order_id,
        'driver_id': user_id
    }, room=f'passenger_{order.passenger_id}')
    
    return jsonify({'status': 'accepted'}), 200


@app.route('/api/driver/orders/<int:order_id>/reject', methods=['POST'])
def reject_order(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user or user.role != UserRole.DRIVER:
        return jsonify({'error': 'Not a driver'}), 403
    
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if order.driver_id != user_id:
        return jsonify({'error': 'Order not assigned to you'}), 403
    
    # Остановить таймер
    if order_id in order_timers:
        del order_timers[order_id]
    
    user.current_order_id = None
    order.driver_id = None
    order.status = OrderStatus.PENDING
    order.assigned_at = None
    db.session.commit()
    
    # Попробовать назначить следующему водителю
    assign_order_to_next_driver(order_id)
    
    return jsonify({'status': 'rejected'}), 200


@app.route('/api/driver/orders/<int:order_id>/start', methods=['POST'])
def start_order(order_id):
    """Пассажир в машине — переход в статус «В пути», уведомление пассажира"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    user = User.query.get(user_id)
    if not user or user.role != UserRole.DRIVER:
        return jsonify({'error': 'Not a driver'}), 403
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    if order.driver_id != user_id:
        return jsonify({'error': 'Order not assigned to you'}), 403
    if order.status != OrderStatus.ACCEPTED:
        return jsonify({'error': 'Заказ уже в пути или завершён'}), 400
    order.status = OrderStatus.IN_PROGRESS
    db.session.commit()
    socketio.emit('order_in_progress', {'order_id': order_id}, room=f'passenger_{order.passenger_id}')
    return jsonify({'status': 'in_progress'}), 200


@app.route('/api/driver/orders/<int:order_id>/complete', methods=['POST'])
def complete_order(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user or user.role != UserRole.DRIVER:
        return jsonify({'error': 'Not a driver'}), 403
    
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if order.driver_id != user_id:
        return jsonify({'error': 'Order not assigned to you'}), 403
    
    ok = order.status in (OrderStatus.ACCEPTED, OrderStatus.IN_PROGRESS)
    if not ok and hasattr(order.status, 'value'):
        ok = order.status.value in ('accepted', 'in_progress')
    if not ok:
        s = getattr(order.status, 'value', str(order.status))
        return jsonify({'error': 'Заказ нельзя завершить (статус: ' + s + '). Сначала примите заказ.'}), 400
    
    order.status = OrderStatus.COMPLETED
    order.completed_at = datetime.utcnow()
    user.current_order_id = None
    db.session.commit()
    
    # Уведомить пассажира
    socketio.emit('order_completed', {
        'order_id': order_id
    }, room=f'passenger_{order.passenger_id}')
    
    return jsonify({'status': 'completed'}), 200


@app.route('/api/passenger/orders', methods=['POST'])
def create_order():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user or user.role != UserRole.PASSENGER:
        return jsonify({'error': 'Not a passenger'}), 403
    
    data = request.json
    pickup_address = data.get('pickup_address')
    destination_address = data.get('destination_address')
    pickup_lat = data.get('pickup_lat')
    pickup_lng = data.get('pickup_lng')
    destination_lat = data.get('destination_lat')
    destination_lng = data.get('destination_lng')
    
    if not pickup_address or not destination_address:
        return jsonify({'error': 'Missing required fields'}), 400
    
    order = Order(
        passenger_id=user_id,
        pickup_address=pickup_address,
        destination_address=destination_address,
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        destination_lat=destination_lat,
        destination_lng=destination_lng,
        status=OrderStatus.PENDING
    )
    db.session.add(order)
    db.session.commit()
    
    # Попробовать назначить водителю
    assign_order_to_next_driver(order.id)
    
    return jsonify({
        'order_id': order.id,
        'status': order.status.value
    }), 201


@app.route('/api/passenger/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if order.passenger_id != user_id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'order_id': order.id,
        'pickup_address': order.pickup_address,
        'destination_address': order.destination_address,
        'pickup_lat': order.pickup_lat,
        'pickup_lng': order.pickup_lng,
        'destination_lat': order.destination_lat,
        'destination_lng': order.destination_lng,
        'status': order.status.value,
        'driver_id': order.driver_id,
        'created_at': order.created_at.isoformat()
    }), 200


@app.route('/api/passenger/orders/<int:order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if order.passenger_id != user_id:
        return jsonify({'error': 'Access denied'}), 403
    
    if order.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
        return jsonify({'error': 'Order cannot be cancelled'}), 400
    
    # Если заказ назначен водителю, освободить его
    if order.driver_id:
        driver = User.query.get(order.driver_id)
        if driver:
            driver.current_order_id = None
        
        # Остановить таймер если есть
        if order_id in order_timers:
            del order_timers[order_id]
        
        # Уведомить водителя
        socketio.emit('order_cancelled', {
            'order_id': order_id
        }, room=f'driver_{order.driver_id}')
    
    order.status = OrderStatus.CANCELLED
    order.driver_id = None
    db.session.commit()
    
    return jsonify({'status': 'cancelled'}), 200


@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            if user.role == UserRole.DRIVER:
                join_room(f'driver_{user_id}')
            elif user.role == UserRole.PASSENGER:
                join_room(f'passenger_{user_id}')
            emit('connected', {'user_id': user_id, 'role': user.role.value})


@socketio.on('driver_register')
def on_driver_register(data):
    """Явная подписка водителя на заказы (на случай, если session в connect не сработала)"""
    user_id = data.get('user_id') if isinstance(data, dict) else None
    if not user_id:
        return
    # Проверка: сессия совпадает или, если сессии нет в socket-контексте, — что пользователь есть и он водитель
    sid = session.get('user_id')
    if sid == user_id:
        pass
    elif sid is None:
        u = User.query.get(user_id)
        if not u or u.role != UserRole.DRIVER:
            return
    else:
        return
    join_room(f'driver_{user_id}')


@socketio.on('disconnect')
def handle_disconnect():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            if user.role == UserRole.DRIVER:
                leave_room(f'driver_{user_id}')
            elif user.role == UserRole.PASSENGER:
                leave_room(f'passenger_{user_id}')


if __name__ == '__main__':
    init_db()
    rebuild_driver_queue()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
