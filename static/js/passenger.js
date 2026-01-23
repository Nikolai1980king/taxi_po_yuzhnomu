// Подключение к WebSocket
const socket = io();
const useYandex = !!(window.USE_YANDEX && typeof ymaps !== 'undefined');

let currentOrderId = null;
let pickup = null;
let destination = null;
let selectStep = 'pickup';

// Leaflet
let map = null;
let pickupMarker = null;
let destinationMarker = null;
let userLocationMarker = null;
// Yandex
let yandexMap = null;
let yandexPickupPlacemark = null;
let yandexDestPlacemark = null;
let yandexUserCircle = null;

const mapEl = document.getElementById('map');
const hintEl = document.getElementById('map-hint');
const myLocationBtn = document.getElementById('my-location-btn');
const pickupInput = document.getElementById('pickup-address');
const pickupCoordsEl = document.getElementById('pickup-coords');
const destInput = document.getElementById('destination-address');
const destCoordsEl = document.getElementById('destination-coords');
const confirmBtn = document.getElementById('confirm-order-btn');
const orderForm = document.getElementById('order-form');
const resetPickupBtn = document.getElementById('reset-pickup-btn');
const resetDestBtn = document.getElementById('reset-dest-btn');

// --- Геокодинг: улица и дом ---
function formatStreetAndHouse(street, house) {
    var parts = [];
    if (street) parts.push(street.indexOf('ул.') === 0 || street.indexOf('улица') === 0 ? street : 'ул. ' + street);
    if (house) parts.push(house.indexOf('д.') === 0 ? house : 'д. ' + house);
    return parts.length ? parts.join(', ') : null;
}

// Обратный геокодинг — всегда Nominatim (как у водителя), карта может быть Яндекс
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

function getCurrentLocation(cb) {
    if (!navigator.geolocation) { cb(null); return; }
    navigator.geolocation.getCurrentPosition(
        function (p) { cb({ lat: p.coords.latitude, lng: p.coords.longitude }); },
        function () { cb(null); },
        { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
    );
}

function onMapClick(lat, lng) {
    if (selectStep === 'pickup') setPickup(lat, lng);
    else if (selectStep === 'destination') setDestination(lat, lng);
}

// --- Установка точек ---
function setPickup(lat, lng) {
    if (useYandex && yandexMap) {
        if (yandexPickupPlacemark) yandexMap.geoObjects.remove(yandexPickupPlacemark);
        yandexPickupPlacemark = new ymaps.Placemark([lat, lng], {}, { preset: 'islands#greenCircleDotIcon' });
        yandexMap.geoObjects.add(yandexPickupPlacemark);
    } else if (map && typeof L !== 'undefined') {
        if (pickupMarker) map.removeLayer(pickupMarker);
        pickupMarker = L.marker([lat, lng], { icon: greenIcon }).addTo(map);
    }
    pickup = { lat: lat, lng: lng, address: null };
    if (pickupCoordsEl) pickupCoordsEl.textContent = lat.toFixed(6) + ', ' + lng.toFixed(6);
    if (pickupInput) { pickupInput.placeholder = 'Загрузка…'; pickupInput.value = ''; }
    reverseGeocode(lat, lng, function (addr) {
        if (pickup) pickup.address = addr;
        if (pickupInput) pickupInput.value = addr;
        if (pickupInput) pickupInput.placeholder = 'Откуда';
        updateConfirmButton();
        updateResetButtons();
    });
    selectStep = 'destination';
    if (hintEl) hintEl.textContent = 'Выберите точку назначения на карте';
    updateConfirmButton();
    updateResetButtons();
}

function setDestination(lat, lng) {
    if (useYandex && yandexMap) {
        if (yandexDestPlacemark) yandexMap.geoObjects.remove(yandexDestPlacemark);
        yandexDestPlacemark = new ymaps.Placemark([lat, lng], {}, { preset: 'islands#redCircleDotIcon' });
        yandexMap.geoObjects.add(yandexDestPlacemark);
    } else if (map && typeof L !== 'undefined') {
        if (destinationMarker) map.removeLayer(destinationMarker);
        destinationMarker = L.marker([lat, lng], { icon: redIcon }).addTo(map);
    }
    destination = { lat: lat, lng: lng, address: null };
    if (destCoordsEl) destCoordsEl.textContent = lat.toFixed(6) + ', ' + lng.toFixed(6);
    if (destInput) { destInput.placeholder = 'Загрузка…'; destInput.value = ''; }
    reverseGeocode(lat, lng, function (addr) {
        if (destination) destination.address = addr;
        if (destInput) destInput.value = addr;
        if (destInput) destInput.placeholder = 'Куда';
        updateConfirmButton();
        updateResetButtons();
    });
    selectStep = 'ready';
    if (hintEl) hintEl.textContent = 'Проверьте адреса и нажмите «Подтвердить»';
    updateConfirmButton();
    updateResetButtons();
}

function updateConfirmButton() {
    var ok = pickup && pickup.address && destination && destination.address;
    if (confirmBtn) confirmBtn.disabled = !ok;
}

function updateResetButtons() {
    if (resetPickupBtn) resetPickupBtn.disabled = !pickup;
    if (resetDestBtn) resetDestBtn.disabled = !destination;
}

// --- Сброс одной точки ---
function clearPickup() {
    if (useYandex && yandexMap && yandexPickupPlacemark) {
        yandexMap.geoObjects.remove(yandexPickupPlacemark);
        yandexPickupPlacemark = null;
    } else if (map && pickupMarker) { map.removeLayer(pickupMarker); pickupMarker = null; }
    pickup = null;
    if (pickupInput) pickupInput.value = '';
    if (pickupCoordsEl) pickupCoordsEl.textContent = '';
    if (pickupInput) pickupInput.placeholder = 'Точка на карте';
    selectStep = destination ? 'destination' : 'pickup';
    if (hintEl) hintEl.textContent = selectStep === 'pickup' ? 'Выберите точку отправления на карте или «Моё местоположение»' : 'Выберите точку назначения на карте';
    updateConfirmButton();
    updateResetButtons();
}

function clearDestination() {
    if (useYandex && yandexMap && yandexDestPlacemark) {
        yandexMap.geoObjects.remove(yandexDestPlacemark);
        yandexDestPlacemark = null;
    } else if (map && destinationMarker) { map.removeLayer(destinationMarker); destinationMarker = null; }
    destination = null;
    if (destInput) destInput.value = '';
    if (destCoordsEl) destCoordsEl.textContent = '';
    if (destInput) destInput.placeholder = 'Точка на карте';
    selectStep = pickup ? 'destination' : 'pickup';
    if (hintEl) hintEl.textContent = selectStep === 'pickup' ? 'Выберите точку отправления на карте или «Моё местоположение»' : 'Выберите точку назначения на карте';
    updateConfirmButton();
    updateResetButtons();
}

if (resetPickupBtn) resetPickupBtn.addEventListener('click', clearPickup);
if (resetDestBtn) resetDestBtn.addEventListener('click', clearDestination);

// --- Leaflet ---
var greenIcon, redIcon;
if (!useYandex && typeof L !== 'undefined') {
    greenIcon = L.divIcon({ className: 'marker-pickup', html: '<div style="background:#22c55e;width:24px;height:24px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 5px rgba(0,0,0,.3)"></div>', iconSize: [24, 24], iconAnchor: [12, 12] });
    redIcon = L.divIcon({ className: 'marker-dest', html: '<div style="background:#ef4444;width:24px;height:24px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 5px rgba(0,0,0,.3)"></div>', iconSize: [24, 24], iconAnchor: [12, 12] });
}

function initLeaflet(center) {
    if (map || !mapEl || typeof L === 'undefined') return;
    var c = center || { lat: 55.75, lng: 37.62 };
    map = L.map('map').setView([c.lat, c.lng], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap' }).addTo(map);
    map.on('click', function (e) { onMapClick(e.latlng.lat, e.latlng.lng); });
}

function initYandex(center) {
    if (yandexMap || !mapEl || typeof ymaps === 'undefined') return;
    var c = center || { lat: 55.75, lng: 37.62 };
    yandexMap = new ymaps.Map('map', { center: [c.lat, c.lng], zoom: 14, controls: ['zoomControl'] });
    yandexMap.events.add('click', function (e) { var coords = e.get('coords'); onMapClick(coords[0], coords[1]); });
}

// --- Моё местоположение ---
function onMyLocation() {
    var m = useYandex ? yandexMap : map;
    if (!m || !myLocationBtn) return;
    myLocationBtn.disabled = true;
    myLocationBtn.textContent = 'Поиск…';
    getCurrentLocation(function (loc) {
        if (myLocationBtn) { myLocationBtn.disabled = false; myLocationBtn.textContent = '📍 Моё местоположение'; }
        if (!loc) {
            alert('Не удалось получить координаты. Разрешите геолокацию или выберите точку на карте.');
            return;
        }
        if (useYandex && yandexMap) {
            yandexMap.setCenter([loc.lat, loc.lng], 16);
            if (yandexUserCircle) yandexMap.geoObjects.remove(yandexUserCircle);
            yandexUserCircle = new ymaps.Circle([[loc.lat, loc.lng], 60], {}, { fillColor: '#3b82f680', strokeColor: '#3b82f6', strokeWidth: 2 });
            yandexMap.geoObjects.add(yandexUserCircle);
        } else if (map) {
            map.setView([loc.lat, loc.lng], 16);
            if (userLocationMarker) map.removeLayer(userLocationMarker);
            userLocationMarker = L.circleMarker([loc.lat, loc.lng], { radius: 8, color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.7, weight: 2 }).addTo(map);
        }
        setPickup(loc.lat, loc.lng);
    });
}
if (myLocationBtn) myLocationBtn.addEventListener('click', onMyLocation);

// --- Инициализация ---
function startOrderForm() {
    if (!mapEl || !hintEl) return;
    var def = { lat: 55.75, lng: 37.62 };
    function afterMap() {
        hintEl.textContent = 'Выберите точку отправления на карте или нажмите «Моё местоположение»';
        updateResetButtons();
        if (!useYandex && map) setTimeout(function () { map.invalidateSize(); }, 300);
        getCurrentLocation(function (loc) {
            if (!loc) return;
            var m = useYandex ? yandexMap : map;
            if (!m) return;
            if (useYandex) { yandexMap.setCenter([loc.lat, loc.lng], 14); } else { map.setView([loc.lat, loc.lng], 14); }
            if (useYandex) {
                if (yandexUserCircle) yandexMap.geoObjects.remove(yandexUserCircle);
                yandexUserCircle = new ymaps.Circle([[loc.lat, loc.lng], 60], {}, { fillColor: '#3b82f680', strokeColor: '#3b82f6', strokeWidth: 2 });
                yandexMap.geoObjects.add(yandexUserCircle);
            } else {
                if (userLocationMarker) map.removeLayer(userLocationMarker);
                userLocationMarker = L.circleMarker([loc.lat, loc.lng], { radius: 8, color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.7, weight: 2 }).addTo(map);
            }
        });
    }
    if (useYandex) {
        hintEl.textContent = 'Загрузка карты…';
        ymaps.ready(function () { initYandex(def); afterMap(); });
    } else {
        if (typeof L === 'undefined') { hintEl.textContent = 'Карта не загрузилась. Проверьте интернет.'; return; }
        hintEl.textContent = 'Загрузка карты…';
        initLeaflet(def);
        afterMap();
    }
}

function resetOrderForm() {
    pickup = null; destination = null; selectStep = 'pickup';
    if (useYandex && yandexMap) {
        if (yandexPickupPlacemark) { yandexMap.geoObjects.remove(yandexPickupPlacemark); yandexPickupPlacemark = null; }
        if (yandexDestPlacemark) { yandexMap.geoObjects.remove(yandexDestPlacemark); yandexDestPlacemark = null; }
        if (yandexUserCircle) { yandexMap.geoObjects.remove(yandexUserCircle); yandexUserCircle = null; }
    } else if (map) {
        if (pickupMarker) { map.removeLayer(pickupMarker); pickupMarker = null; }
        if (destinationMarker) { map.removeLayer(destinationMarker); destinationMarker = null; }
        if (userLocationMarker) { map.removeLayer(userLocationMarker); userLocationMarker = null; }
    }
    if (pickupInput) pickupInput.value = '';
    if (pickupCoordsEl) pickupCoordsEl.textContent = '';
    if (destInput) destInput.value = '';
    if (destCoordsEl) destCoordsEl.textContent = '';
    if (hintEl) hintEl.textContent = 'Выберите точку отправления на карте или нажмите «Моё местоположение»';
    if (confirmBtn) confirmBtn.disabled = true;
    updateResetButtons();
    if (!useYandex && map) setTimeout(function () { map.invalidateSize(); }, 150);
}

// --- Подтверждение заказа ---
orderForm.addEventListener('submit', function (e) {
    e.preventDefault();
    if (!pickup || !pickup.address || !destination || !destination.address) { alert('Выберите точки на карте'); return; }
    var pa = pickup.address + ' (' + pickup.lat.toFixed(6) + ', ' + pickup.lng.toFixed(6) + ')';
    var da = destination.address + ' (' + destination.lat.toFixed(6) + ', ' + destination.lng.toFixed(6) + ')';
    fetch('/api/passenger/orders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pickup_address: pa, destination_address: da, pickup_lat: pickup.lat, pickup_lng: pickup.lng, destination_lat: destination.lat, destination_lng: destination.lng }) })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.order_id) {
                currentOrderId = data.order_id;
                showOrderStatus(data.order_id, pa, da, pickup.lat, pickup.lng, destination.lat, destination.lng);
                document.getElementById('order-form-section').style.display = 'none';
            } else alert(data.error || 'Ошибка');
        })
        .catch(function () { alert('Ошибка создания заказа'); });
});

function showOrderStatus(orderId, pa, da, pickupLat, pickupLng, destLat, destLng) {
    var pEl = document.getElementById('status-pickup');
    var dEl = document.getElementById('status-destination');
    resolveAddress(pEl, pickupLat, pickupLng, pa);
    resolveAddress(dEl, destLat, destLng, da);
    document.getElementById('status-text').textContent = 'Ожидание водителя';
    updateStatusStep('pending', true); updateStatusStep('assigned', false); updateStatusStep('accepted', false); updateStatusStep('completed', false);
    document.getElementById('order-status-section').style.display = 'block';
    var b = document.getElementById('cancel-order-btn'); if (b) b.style.display = 'block';
}

function updateStatusStep(step, active) {
    var el = document.getElementById('step-' + step); if (!el) return;
    if (active) el.classList.add('active'); else el.classList.remove('active', 'completed');
}

document.getElementById('cancel-order-btn').addEventListener('click', function () {
    if (!currentOrderId) return; if (!confirm('Отменить заказ?')) return;
    fetch('/api/passenger/orders/' + currentOrderId + '/cancel', { method: 'POST' }).then(function (r) { return r.json(); }).then(function (d) {
        if (d.status === 'cancelled') { document.getElementById('status-text').textContent = 'Отменено'; document.getElementById('cancel-order-btn').style.display = 'none'; currentOrderId = null;
            setTimeout(function () { document.getElementById('order-status-section').style.display = 'none'; document.getElementById('order-form-section').style.display = 'block'; resetOrderForm(); }, 2000); }
        else alert(d.error || 'Ошибка');
    }).catch(function () { alert('Ошибка'); });
});

socket.on('connect', function () {});
socket.on('queue_updated', function (d) {
    applyDriversCount(d);
});

function applyDriversCount(d) {
    var count = 0;
    if (d && d.count != null) count = Number(d.count) || 0;
    else if (d && Array.isArray(d.queue)) count = d.queue.length;
    var wrap = document.getElementById('drivers-count-wrap');
    var el = document.getElementById('drivers-online-count');
    if (el) el.textContent = String(count);
    if (wrap) wrap.style.display = count > 0 ? 'block' : 'none';
}
socket.on('order_assigned', function (d) { if (currentOrderId !== d.order_id) return; document.getElementById('status-text').textContent = 'Водитель назначен'; updateStatusStep('pending', false); updateStatusStep('assigned', true); });
socket.on('order_accepted', function (d) { if (currentOrderId !== d.order_id) return; document.getElementById('status-text').textContent = 'Водитель принял'; updateStatusStep('assigned', false); updateStatusStep('accepted', true); document.getElementById('cancel-order-btn').style.display = 'none'; });
socket.on('order_in_progress', function (d) { if (currentOrderId !== d.order_id) return; document.getElementById('status-text').textContent = 'В пути к месту назначения'; });
socket.on('order_completed', function (d) {
    if (currentOrderId !== d.order_id) return;
    document.getElementById('status-text').textContent = 'Завершено'; updateStatusStep('accepted', false); updateStatusStep('completed', true); document.getElementById('cancel-order-btn').style.display = 'none';
    setTimeout(function () { currentOrderId = null; document.getElementById('order-status-section').style.display = 'none'; document.getElementById('order-form-section').style.display = 'block'; resetOrderForm(); }, 3000);
});

setInterval(function () {
    if (!currentOrderId) return;
    fetch('/api/passenger/orders/' + currentOrderId).then(function (r) { return r.json(); }).then(function (d) {
        document.getElementById('status-text').textContent = ({ pending: 'Ожидание водителя', assigned: 'Водитель назначен', accepted: 'Водитель принял', in_progress: 'В пути', completed: 'Завершено', cancelled: 'Отменено' })[d.status] || d.status;
        updateStatusStep('pending', d.status === 'pending'); updateStatusStep('assigned', ['assigned','accepted','in_progress','completed'].indexOf(d.status) >= 0); updateStatusStep('accepted', ['accepted','in_progress','completed'].indexOf(d.status) >= 0); updateStatusStep('completed', d.status === 'completed');
        if (['completed','cancelled'].indexOf(d.status) >= 0) document.getElementById('cancel-order-btn').style.display = 'none';
    }).catch(function () {});
}, 5000);

fetch('/api/drivers/online_count').then(function (r) { return r.json(); }).then(function (d) {
    applyDriversCount({ count: d && d.count != null ? d.count : 0 });
}).catch(function () {});

// Fallback: обновление счетчика, если socket-события пропали
setInterval(function () {
    fetch('/api/queue').then(function (r) { return r.json(); }).then(function (d) {
        applyDriversCount(d);
    }).catch(function () {});
}, 3000);

var elSwitchDriver = document.getElementById('switch-to-driver');
if (elSwitchDriver) elSwitchDriver.addEventListener('click', function (e) {
    e.preventDefault();
    fetch('/api/me/switch-role', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({role: 'driver'}) })
        .then(function (r) { return r.json(); })
        .then(function (d) { if (d.role) window.location.href = '/driver'; else alert(d.error || 'Ошибка'); })
        .catch(function () { alert('Ошибка сети'); });
});

document.addEventListener('DOMContentLoaded', startOrderForm);