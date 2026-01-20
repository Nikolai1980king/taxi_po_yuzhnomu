// Подключение к WebSocket
const socket = io();

let currentOrder = null;
let driverUserId = null;
let orderTimer = null;
let timeLeft = 60;

// --- Обратный геокодинг: улица и дом (Nominatim) ---
function formatStreetAndHouse(street, house) {
    var parts = [];
    if (street) parts.push(street.indexOf('ул.') === 0 || street.indexOf('улица') === 0 ? street : 'ул. ' + street);
    if (house) parts.push(house.indexOf('д.') === 0 ? house : 'д. ' + house);
    return parts.length ? parts.join(', ') : null;
}

function reverseGeocode(lat, lng, callback) {
    var fallback = lat.toFixed(6) + ', ' + lng.toFixed(6);
    fetch('https://nominatim.openstreetmap.org/reverse?lat=' + lat + '&lon=' + lng + '&format=json', { headers: { 'Accept-Language': 'ru' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var a = data.address || {};
            var street = a.road || a.street || a.pedestrian || a.footway;
            var house = a.house_number || a.house;
            var addr = formatStreetAndHouse(street, house) || data.display_name || fallback;
            callback(addr);
        })
        .catch(function () { callback(fallback); });
}

function resolveAddress(el, lat, lng, fallback) {
    if (!el) return;
    if (lat != null && lng != null) {
        el.textContent = 'Загрузка адреса…';
        reverseGeocode(lat, lng, function (addr) { el.textContent = addr; });
    } else {
        el.textContent = fallback || '';
    }
}

// Загрузка информации о водителе
async function loadDriverInfo() {
    try {
        // Проверка текущего заказа
        await checkCurrentOrder();
    } catch (error) {
        console.error('Ошибка загрузки информации:', error);
    }
}

// Проверка текущего заказа
async function checkCurrentOrder() {
    try {
        const response = await fetch('/api/driver/orders/current');
        const data = await response.json();
        if (data.order_id) {
            var ord = { id: data.order_id, order_id: data.order_id, pickup_address: data.pickup_address, destination_address: data.destination_address, pickup_lat: data.pickup_lat, pickup_lng: data.pickup_lng, destination_lat: data.destination_lat, destination_lng: data.destination_lng, assigned_at: data.assigned_at };
            if (data.status === 'accepted' || data.status === 'in_progress') {
                currentOrder = ord;
                showAcceptedOrder(ord);
            } else {
                showOrder(data);
            }
        } else {
            showNoOrders();
        }
    } catch (error) {
        console.error('Ошибка проверки заказа:', error);
    }
}

// Переключение статуса онлайн/офлайн
document.getElementById('toggle-status-btn').addEventListener('click', async () => {
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    const statusDot = statusIndicator.querySelector('.status-dot');
    const btn = document.getElementById('toggle-status-btn');
    const queueInfo = document.getElementById('queue-info');
    
    const isOnline = statusDot.classList.contains('online');
    
    try {
        const endpoint = isOnline ? '/api/driver/offline' : '/api/driver/online';
        const response = await fetch(endpoint, {method: 'POST'});
        const data = await response.json();
        
        if (response.ok) {
            if (isOnline) {
                statusDot.classList.remove('online');
                statusDot.classList.add('offline');
                statusText.textContent = 'Офлайн';
                btn.textContent = 'Выйти на линию';
                queueInfo.style.display = 'none';
                hideOrder();
            } else {
                statusDot.classList.remove('offline');
                statusDot.classList.add('online');
                statusText.textContent = 'Онлайн';
                btn.textContent = 'Выйти из линии';
                if (data.queue_position) {
                    document.getElementById('queue-position').textContent = data.queue_position;
                    queueInfo.style.display = 'block';
                }
            }
        }
    } catch (error) {
        console.error('Ошибка изменения статуса:', error);
        alert('Ошибка изменения статуса');
    }
});

// Принятие заказа
document.getElementById('accept-order-btn').addEventListener('click', async () => {
    if (!currentOrder) return;
    
    try {
        const response = await fetch(`/api/driver/orders/${currentOrder.id}/accept`, {
            method: 'POST'
        });
        
        if (response.ok) {
            clearOrderTimer();
            showAcceptedOrder(currentOrder);
            socket.emit('order_accepted', {order_id: currentOrder.id});
        } else {
            const data = await response.json();
            alert(data.error || 'Ошибка принятия заказа');
        }
    } catch (error) {
        console.error('Ошибка принятия заказа:', error);
        alert('Ошибка принятия заказа');
    }
});

// Отклонение заказа
document.getElementById('reject-order-btn').addEventListener('click', async () => {
    if (!currentOrder) return;
    
    if (!confirm('Вы уверены, что хотите отклонить заказ?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/driver/orders/${currentOrder.id}/reject`, {
            method: 'POST'
        });
        
        if (response.ok) {
            clearOrderTimer();
            hideOrder();
            currentOrder = null;
        } else {
            const data = await response.json();
            alert(data.error || 'Ошибка отклонения заказа');
        }
    } catch (error) {
        console.error('Ошибка отклонения заказа:', error);
        alert('Ошибка отклонения заказа');
    }
});

// Завершение заказа — вызывается по onclick с кнопки
window.doCompleteOrder = function doCompleteOrder() {
    var id = currentOrder && (currentOrder.id || currentOrder.order_id);
    if (!id) { alert('Нет активного заказа'); return; }
    var btn = document.getElementById('complete-order-btn');
    if (btn) btn.disabled = true;
    fetch('/api/driver/orders/' + String(id) + '/complete', { method: 'POST', credentials: 'same-origin' })
        .then(function (r) {
            if (r.ok) { hideOrder(); currentOrder = null; alert('Заказ завершён'); return; }
            return r.json().then(function (d) { alert(d.error || 'Ошибка'); }, function () { alert('Ошибка сервера: ' + r.status); });
        })
        .catch(function (err) { console.error(err); alert('Ошибка сети'); })
        .finally(function () { if (btn) btn.disabled = false; });
};

// Показать заказ (orderData: order_id, pickup_address, destination_address, pickup_lat, pickup_lng, destination_lat, destination_lng, assigned_at)
function showOrder(orderData) {
    currentOrder = {
        id: orderData.order_id || orderData.id,
        pickup_address: orderData.pickup_address,
        destination_address: orderData.destination_address,
        pickup_lat: orderData.pickup_lat,
        pickup_lng: orderData.pickup_lng,
        destination_lat: orderData.destination_lat,
        destination_lng: orderData.destination_lng,
        assigned_at: orderData.assigned_at
    };
    
    var pickupEl = document.getElementById('order-pickup');
    var destEl = document.getElementById('order-destination');
    resolveAddress(pickupEl, orderData.pickup_lat, orderData.pickup_lng, orderData.pickup_address);
    resolveAddress(destEl, orderData.destination_lat, orderData.destination_lng, orderData.destination_address);
    
    document.getElementById('order-section').style.display = 'block';
    document.getElementById('accepted-order-section').style.display = 'none';
    document.getElementById('no-orders').style.display = 'none';
    
    // Запустить таймер
    if (currentOrder.assigned_at) {
        const assignedTime = new Date(currentOrder.assigned_at);
        const now = new Date();
        const elapsed = Math.floor((now - assignedTime) / 1000);
        timeLeft = Math.max(0, 60 - elapsed);
    } else {
        timeLeft = 60;
    }
    
    startOrderTimer();
}

// Показать принятый заказ
function showAcceptedOrder(orderData) {
    var pEl = document.getElementById('accepted-pickup');
    var dEl = document.getElementById('accepted-destination');
    resolveAddress(pEl, orderData.pickup_lat, orderData.pickup_lng, orderData.pickup_address);
    resolveAddress(dEl, orderData.destination_lat, orderData.destination_lng, orderData.destination_address);
    var st = document.getElementById('accepted-status');
    if (st) st.textContent = 'Принят';
    
    document.getElementById('order-section').style.display = 'none';
    document.getElementById('accepted-order-section').style.display = 'block';
    document.getElementById('no-orders').style.display = 'none';
}

// Скрыть заказ
function hideOrder() {
    document.getElementById('order-section').style.display = 'none';
    document.getElementById('accepted-order-section').style.display = 'none';
    document.getElementById('no-orders').style.display = 'block';
    currentOrder = null;
}

// Показать отсутствие заказов
function showNoOrders() {
    hideOrder();
}

// Таймер заказа
function startOrderTimer() {
    clearOrderTimer();
    
    const timerElement = document.getElementById('order-timer');
    
    orderTimer = setInterval(() => {
        timeLeft--;
        
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        timerElement.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        
        if (timeLeft <= 0) {
            clearOrderTimer();
            hideOrder();
        }
    }, 1000);
}

function clearOrderTimer() {
    if (orderTimer) {
        clearInterval(orderTimer);
        orderTimer = null;
    }
    timeLeft = 60;
    document.getElementById('order-timer').textContent = '00:60';
}

// WebSocket события
socket.on('connect', () => {
    if (driverUserId) socket.emit('driver_register', { user_id: driverUserId });
});

socket.on('new_order', function (data) {
    showOrder({
        id: data.order_id,
        order_id: data.order_id,
        pickup_address: data.pickup_address,
        destination_address: data.destination_address,
        pickup_lat: data.pickup_lat,
        pickup_lng: data.pickup_lng,
        destination_lat: data.destination_lat,
        destination_lng: data.destination_lng,
        assigned_at: data.assigned_at
    });
});

socket.on('order_timeout', (data) => {
    if (currentOrder && currentOrder.id === data.order_id) {
        hideOrder();
        alert('Время на принятие заказа истекло');
    }
});

socket.on('queue_updated', (data) => {
    // Обновить информацию об очереди если нужно
    console.log('Очередь обновлена:', data.queue);
});

// Загрузка информации о пользователе и подписка на заказы
async function loadUserInfo() {
    try {
        const response = await fetch('/api/user/current');
        if (response.ok) {
            const data = await response.json();
            if (data.role === 'driver') {
                driverUserId = data.user_id;
                socket.emit('driver_register', { user_id: data.user_id });
                const info = document.getElementById('driver-info');
                if (info) info.textContent = 'Водитель: ' + (data.username || '');
                if (data.is_online) {
                    const statusDot = document.querySelector('.status-dot');
                    const statusText = document.getElementById('status-text');
                    const btn = document.getElementById('toggle-status-btn');
                    const queueInfo = document.getElementById('queue-info');
                    if (statusDot) { statusDot.classList.remove('offline'); statusDot.classList.add('online'); }
                    if (statusText) statusText.textContent = 'Онлайн';
                    if (btn) btn.textContent = 'Выйти из линии';
                    if (data.queue_position != null) {
                        const qp = document.getElementById('queue-position');
                        if (qp) qp.textContent = data.queue_position;
                        if (queueInfo) queueInfo.style.display = 'block';
                    }
                }
            }
        }
    } catch (e) {
        console.error('Ошибка загрузки информации о пользователе:', e);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    loadUserInfo();
    loadDriverInfo();
    // Периодическая проверка текущего заказа (если сокет не доставил new_order)
    setInterval(() => {
        if (!currentOrder) checkCurrentOrder();
    }, 5000);
});
