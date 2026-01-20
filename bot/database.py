import aiosqlite
from datetime import datetime
from typing import Optional

from bot.config import DB_PATH, ORDER_SEARCHING, ROLE_DRIVER, ROLE_PASSENGER


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                role TEXT NOT NULL,
                car_info TEXT,
                is_driver_online INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passenger_id INTEGER NOT NULL,
                driver_id INTEGER,
                from_address TEXT NOT NULL,
                to_address TEXT NOT NULL,
                comment TEXT,
                status TEXT NOT NULL DEFAULT 'searching',
                created_at TEXT NOT NULL,
                accepted_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (passenger_id) REFERENCES users(id),
                FOREIGN KEY (driver_id) REFERENCES users(id)
            )
        """)
        await db.commit()


# --- Пользователи ---

async def get_user(telegram_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(
    telegram_id: int,
    role: str,
    username: str | None = None,
    first_name: str | None = None,
    car_info: str | None = None,
) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO users (telegram_id, username, first_name, role, car_info, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (telegram_id, username or "", first_name or "", role, car_info or "", now),
        )
        await db.commit()
        return cur.lastrowid


async def update_user_role(telegram_id: int, new_role: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET role = ? WHERE telegram_id = ?", (new_role, telegram_id))
        await db.commit()


async def set_driver_online(telegram_id: int, online: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_driver_online = ? WHERE telegram_id = ?",
            (1 if online else 0, telegram_id),
        )
        await db.commit()


async def get_online_drivers() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM users WHERE role = ? AND is_driver_online = 1""",
            (ROLE_DRIVER,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# --- Заказы ---

async def create_order(
    passenger_telegram_id: int,
    from_address: str,
    to_address: str,
    comment: str | None = None,
) -> int:
    user = await get_user(passenger_telegram_id)
    if not user:
        raise ValueError("User not found")
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO orders (passenger_id, from_address, to_address, comment, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user["id"], from_address, to_address, comment or "", ORDER_SEARCHING, now),
        )
        await db.commit()
        return cur.lastrowid


async def get_order(order_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT o.*, p.telegram_id as passenger_telegram_id, d.telegram_id as driver_telegram_id "
            "FROM orders o "
            "JOIN users p ON o.passenger_id = p.id "
            "LEFT JOIN users d ON o.driver_id = d.id "
            "WHERE o.id = ?",
            (order_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_orders_by_passenger(telegram_id: int, status: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            async with db.execute(
                """SELECT o.*, d.first_name as driver_name, d.telegram_id as driver_telegram_id
                   FROM orders o
                   LEFT JOIN users d ON o.driver_id = d.id
                   JOIN users p ON o.passenger_id = p.id
                   WHERE p.telegram_id = ? AND o.status = ?
                   ORDER BY o.created_at DESC""",
                (telegram_id, status),
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
        async with db.execute(
            """SELECT o.*, d.first_name as driver_name, d.telegram_id as driver_telegram_id
               FROM orders o
               LEFT JOIN users d ON o.driver_id = d.id
               JOIN users p ON o.passenger_id = p.id
               WHERE p.telegram_id = ?
               ORDER BY o.created_at DESC
               LIMIT 20""",
            (telegram_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_expired_searching_orders(limit_minutes: int = 5) -> list[dict]:
    """Заказы в статусе searching, созданные более limit_minutes минут назад."""
    now = datetime.utcnow()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.id, o.created_at, p.telegram_id as passenger_telegram_id
               FROM orders o
               JOIN users p ON o.passenger_id = p.id
               WHERE o.status = ?""",
            (ORDER_SEARCHING,),
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        try:
            created = datetime.fromisoformat(str(r["created_at"]).replace("Z", ""))
        except (ValueError, TypeError):
            continue
        if (now - created).total_seconds() >= limit_minutes * 60:
            result.append({"id": r["id"], "passenger_telegram_id": r["passenger_telegram_id"]})
    return result


async def get_available_orders() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.*, p.first_name as passenger_name, p.telegram_id as passenger_telegram_id
               FROM orders o
               JOIN users p ON o.passenger_id = p.id
               WHERE o.status = ?
               ORDER BY o.created_at ASC""",
            (ORDER_SEARCHING,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_driver_active_order(telegram_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.*, p.first_name as passenger_name, p.telegram_id as passenger_telegram_id
               FROM orders o
               JOIN users d ON o.driver_id = d.id
               JOIN users p ON o.passenger_id = p.id
               WHERE d.telegram_id = ? AND o.status IN ('accepted', 'driver_coming', 'in_progress')
               ORDER BY o.created_at DESC
               LIMIT 1""",
            (telegram_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def accept_order(order_id: int, driver_telegram_id: int) -> bool:
    user = await get_user(driver_telegram_id)
    if not user:
        return False
    order = await get_order(order_id)
    if not order or order["status"] != ORDER_SEARCHING:
        return False
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET driver_id = ?, status = 'accepted', accepted_at = ? WHERE id = ?",
            (user["id"], now, order_id),
        )
        await db.commit()
    return True


async def update_order_status(order_id: int, status: str) -> bool:
    now = datetime.utcnow().isoformat()
    col = "completed_at" if status == "completed" else None
    async with aiosqlite.connect(DB_PATH) as db:
        if col:
            await db.execute(
                "UPDATE orders SET status = ?, completed_at = ? WHERE id = ?",
                (status, now, order_id),
            )
        else:
            await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()
    return True


async def cancel_order_if_searching(order_id: int) -> bool:
    """Отменяет заказ только если он ещё в статусе searching. Возвращает True, если отменён."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE orders SET status = 'cancelled' WHERE id = ? AND status = ?",
            (order_id, ORDER_SEARCHING),
        )
        await db.commit()
        return cur.rowcount > 0


async def cancel_order(order_id: int, by_passenger: bool = True) -> bool:
    order = await get_order(order_id)
    if not order:
        return False
    if order["status"] not in (ORDER_SEARCHING, ORDER_ACCEPTED):
        return False
    return await update_order_status(order_id, "cancelled")
