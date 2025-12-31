import aiosqlite

DB_PATH = "bot_data.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER DEFAULT 0,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'menu',
                order_index INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                button_id INTEGER,
                type TEXT,
                file_id TEXT,
                text TEXT,
                media_group_id TEXT,
                FOREIGN KEY (button_id) REFERENCES buttons (id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)
        await db.commit()

async def add_button(name, parent_id=0, b_type='menu'):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT MAX(order_index) FROM buttons WHERE parent_id = ?", (parent_id,)) as cursor:
            row = await cursor.fetchone()
            max_order = row[0] if row[0] is not None else -1
        await db.execute("INSERT INTO buttons (name, parent_id, type, order_index) VALUES (?, ?, ?, ?)", 
                         (name, parent_id, b_type, max_order + 1))
        await db.commit()

async def get_buttons(parent_id=0):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, type, order_index FROM buttons WHERE parent_id = ? ORDER BY order_index ASC, id ASC", (parent_id,)) as cursor:
            return await cursor.fetchall()

async def delete_button(button_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM buttons WHERE id = ?", (button_id,))
        await db.execute("DELETE FROM content WHERE button_id = ?", (button_id,))
        await db.commit()

async def add_content(button_id, c_type, file_id=None, text=None, media_group_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO content (button_id, type, file_id, text, media_group_id) VALUES (?, ?, ?, ?, ?)", 
                         (button_id, c_type, file_id, text, media_group_id))
        await db.commit()

async def get_content(button_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT type, file_id, text, media_group_id FROM content WHERE button_id = ?", (button_id,)) as cursor:
            return await cursor.fetchall()

async def is_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def add_admin(user_id, username=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)", (user_id, username))
        await db.commit()

async def move_button(button_id, direction):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT parent_id, order_index FROM buttons WHERE id = ?", (button_id,)) as cursor:
            row = await cursor.fetchone()
            if not row: return
            parent_id, current_order = row
        
        if direction in ["up", "left"]:
            async with db.execute("SELECT id, order_index FROM buttons WHERE parent_id = ? AND order_index < ? ORDER BY order_index DESC LIMIT 1", (parent_id, current_order)) as cursor:
                target = await cursor.fetchone()
            if not target: # Loop to bottom
                async with db.execute("SELECT id, order_index FROM buttons WHERE parent_id = ? ORDER BY order_index DESC LIMIT 1", (parent_id,)) as cursor:
                    target = await cursor.fetchone()
        elif direction in ["down", "right"]:
            async with db.execute("SELECT id, order_index FROM buttons WHERE parent_id = ? AND order_index > ? ORDER BY order_index ASC LIMIT 1", (parent_id, current_order)) as cursor:
                target = await cursor.fetchone()
            if not target: # Loop to top
                async with db.execute("SELECT id, order_index FROM buttons WHERE parent_id = ? ORDER BY order_index ASC LIMIT 1", (parent_id,)) as cursor:
                    target = await cursor.fetchone()
        else:
            return
            
        if target:
            target_id, target_order = target
            await db.execute("UPDATE buttons SET order_index = ? WHERE id = ?", (target_order, button_id))
            await db.execute("UPDATE buttons SET order_index = ? WHERE id = ?", (current_order, target_id))
            await db.commit()

async def rename_button(button_id, new_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE buttons SET name = ? WHERE id = ?", (new_name, button_id))
        await db.commit()
