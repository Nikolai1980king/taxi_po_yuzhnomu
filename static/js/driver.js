// Подключение к WebSocket
const socket = io();

let currentOrder = null;
let driverUserId = null;
let orderTimer = null;
let timeLeft = 60;
let driverMap = null;
let driverRoute = null;
let navStage = 'to_pickup';

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
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: 'temp'}) // В реальном приложении использовать сессию
        });
        
        // Проверка текущего заказа
        await checkCurrentOrder();
    } catch (error) {
        console.error('Ошибка загрузки информации:', error);
    }
}
        if (data.order_id) {
            var ord = { id: data.order_id, order_id: data.order_id, pickup_address: data.pickup_address, destination_address: data.destination_address, pickup_lat: data.pickup_lat, pickup_lng: data.pickup_lng, destination_lat: data.destination_lat, destination_lng: data.destination_lng, assigned_at: data.assigned_at, status: data.status };
            if (data.status === 'accepted' || data.status === 'in_progress') {
                currentOrder = ord;
                showAcceptedOrder(ord);
            } else {
                showOrder(data);
            }
    try {
        const response = await fetch('/api/driver/orders/current');
        const data = await response.json();
        
        if (data.order_id) {
            showOrder(data);
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
// Показать заказ
function showOrder(orderData) {
    currentOrder = orderData;
    
    document.getElementById('order-pickup').textContent = orderData.pickup_address;
    document.getElementById('order-destination').textContent = orderData.destination_address;
    if (currentOrder.assigned_at) {
        const assignedTime = new Date(currentOrder.assigned_at);
    document.getElementById('accepted-order-section').style.display = 'none';
    document.getElementById('no-orders').style.display = 'none';
    
    // Запустить таймер
    if (orderData.assigned_at) {
        const assignedTime = new Date(orderData.assigned_at);
        const now = new Date();
        const elapsed = Math.floor((now - assignedTime) / 1000);
        timeLeft = Math.max(0, 60 - elapsed);
    } else {
// Показать принятый заказ (stage: to_pickup | to_destination, по умолчанию из orderData.status)
function showAcceptedOrder(orderData) {
    var stage = (orderData.status === 'in_progress') ? 'to_destination' : 'to_pickup';
    navStage = stage;
    
    var pEl = document.getElementById('accepted-pickup');
    var dEl = document.getElementById('accepted-destination');
    resolveAddress(pEl, orderData.pickup_lat, orderData.pickup_lng, orderData.pickup_address);
    resolveAddress(dEl, orderData.destination_lat, orderData.destination_lng, orderData.destination_address);
    var st = document.getElementById('accepted-status');
    if (st) st.textContent = (stage === 'to_pickup') ? 'К пассажиру' : 'В пути к месту назначения';
    
    var stageEl = document.getElementById('driver-nav-stage');
    if (stageEl) stageEl.textContent = (stage === 'to_pickup') ? 'Маршрут до пассажира' : 'Маршрут до места назначения';
    
    var btnPassenger = document.getElementById('passenger-in-car-btn');
    var btnComplete = document.getElementById('complete-order-btn');
    if (btnPassenger) btnPassenger.style.display = (stage === 'to_pickup') ? 'inline-block' : 'none';
    if (btnComplete) btnComplete.style.display = (stage === 'to_destination') ? 'inline-block' : 'none';
    
    document.getElementById('order-section').style.display = 'none';
    document.getElementById('accepted-order-section').style.display = 'block';
    document.getElementById('no-orders').style.display = 'none';
    
    initDriverMap(orderData, stage);
}

function setDriverMapHint(msg) {
    var el = document.getElementById('driver-map-hint');
    if (el) el.textContent = msg || '';
}

function addPlacemarksOnly(map, points) {
    if (!map || typeof ymaps === 'undefined' || !points || points.length === 0) return;
    points.forEach(function (p, i) {
        var pm = new ymaps.Placemark(p, { hintContent: i === 0 ? 'Откуда' : 'Куда' }, { preset: 'islands#redCircleIcon' });
        map.geoObjects.add(pm);
    });
    if (points.length >= 2) {
        var minLat = Math.min(points[0][0], points[1][0]);
        var maxLat = Math.max(points[0][0], points[1][0]);
        var minLng = Math.min(points[0][1], points[1][1]);
        var maxLng = Math.max(points[0][1], points[1][1]);
        map.setBounds([[minLat, minLng], [maxLat, maxLng]], { checkZoomRange: true, duration: 200 });
    }
}

function initDriverMap(orderData, stage) {
    if (!window.DRIVER_HAS_YANDEX) {
        setDriverMapHint('Карта недоступна (нет ключа Яндекс.Карт)');
        return;
    }
    if (typeof ymaps === 'undefined') {
        setDriverMapHint('Загрузка карты… (обновите, если не появилась)');
        return;
    }
    setDriverMapHint('');
    var pickup = [orderData.pickup_lat, orderData.pickup_lng];
    var dest = [orderData.destination_lat, orderData.destination_lng];
    ymaps.ready(function () {
        if (!document.getElementById('driver-route-map')) return;
        if (!driverMap) {
            driverMap = new ymaps.Map('driver-route-map', { center: pickup, zoom: 14 });
        }
        if (driverRoute) {
            driverMap.geoObjects.remove(driverRoute);
            driverRoute = null;
        }
        if (stage === 'to_pickup') {
            navigator.geolocation.getCurrentPosition(
                function (pos) {
                    var from = [pos.coords.latitude, pos.coords.longitude];
                    ymaps.route([from, pickup]).then(function (route) {
                        driverRoute = route;
                        driverMap.geoObjects.add(route);
                        route.getBounds().then(function (b) {
                            if (driverMap) driverMap.setBounds(b, { checkZoomRange: true, duration: 300 });
                        });
                    }).catch(function () {
                        addPlacemarksOnly(driverMap, [from, pickup]);
                    });
                },
                function () {
                    setDriverMapHint('Разрешите геолокацию для маршрута до пассажира.');
                    addPlacemarksOnly(driverMap, [pickup, dest]);
                }
            );
        } else {
            ymaps.route([pickup, dest]).then(function (route) {
                driverRoute = route;
                driverMap.geoObjects.add(route);
                route.getBounds().then(function (b) {
                    if (driverMap) driverMap.setBounds(b, { checkZoomRange: true, duration: 300 });
                });
            }).catch(function () {
                addPlacemarksOnly(driverMap, [pickup, dest]);
            });
        }
    });
}

window.doPassengerInCar = function doPassengerInCar() {
    var id = currentOrder && (currentOrder.id || currentOrder.order_id);
    if (!id) { alert('Нет активного заказа'); return; }
    var btn = document.getElementById('passenger-in-car-btn');
    if (btn) btn.disabled = true;
    fetch('/api/driver/orders/' + String(id) + '/start', { method: 'POST', credentials: 'same-origin' })
        .then(function (r) {
            if (r.ok) {
                currentOrder.status = 'in_progress';
                showAcceptedOrder(currentOrder);
            } else {
                return r.json().then(function (d) { alert(d.error || 'Ошибка'); });
            }
        })
        .catch(function (err) { console.error(err); alert('Ошибка сети'); })
        .finally(function () { if (btn) btn.disabled = false; });
};
    document.getElementById('accepted-status').textContent = 'Принят';
    
    document.getElementById('order-section').style.display = 'none';
    if (driverMap) {
        try { driverMap.destroy(); } catch (e) {}
        driverMap = null;
    }
    driverRoute = null;
    setDriverMapHint('');
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
    if (driverUserId) socket.emit('driver_register', { user_id: driverUserId });
    document.getElementById('order-timer').textContent = '00:60';
}
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

socket.on('new_order', (data) => {
    showOrder({
        id: data.order_id,
        pickup_address: data.pickup_address,
        destination_address: data.destination_address,
        assigned_at: data.assigned_at
    });
});

socket.on('order_timeout', (data) => {
    if (currentOrder && currentOrder.id === data.order_id) {
        hideOrder();
        alert('Время на принятие заказа истекло');
    }
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