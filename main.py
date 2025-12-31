import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from database import (
    init_db, get_buttons, get_content, is_admin, add_admin,
    add_button, delete_button, add_content, move_button,
    rename_button, DB_PATH
)
import aiosqlite

# ===============================
# Bot Token from Environment
# ===============================
TOKEN = os.getenv("BOT_TOKEN")

# Logging
logging.basicConfig(level=logging.INFO)

# Bot and Dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ===============================
# States
# ===============================
class BotStates(StatesGroup):
    adding_button = State()
    adding_post = State()
    managing_admins = State()
    renaming_button = State()

# ===============================
# Helper: Reply Keyboard
# ===============================
async def build_reply_keyboard(parent_id=0, user_id=None, editor_mode=None):
    is_user_admin = await is_admin(user_id) if user_id else False
    buttons = await get_buttons(parent_id)
    builder = ReplyKeyboardBuilder()

    for b_id, name, b_type, order in buttons:
        builder.add(types.KeyboardButton(text=name))

    builder.adjust(2)

    nav_row = []

    if parent_id != 0:
        nav_row.append(types.KeyboardButton(text="🔙 Back"))
        nav_row.append(types.KeyboardButton(text="🏠 Main Menu"))

    if is_user_admin:
        if editor_mode:
            nav_row.append(types.KeyboardButton(text="🛑 Stop Editing"))
        else:
            if parent_id == 0:
                nav_row.append(types.KeyboardButton(text="⚙️ Buttons Editor"))
                nav_row.append(types.KeyboardButton(text="✍️ Posts Editor"))
                nav_row.append(types.KeyboardButton(text="👥 Admins"))
            else:
                nav_row.append(types.KeyboardButton(text="⚙️ Buttons Editor"))
                nav_row.append(types.KeyboardButton(text="✍️ Posts Editor"))

    if nav_row:
        builder.row(*nav_row)

    return builder.as_markup(resize_keyboard=True)

# ===============================
# Start Command
# ===============================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await init_db()
    await add_admin(1579607914, "ALZ_hraa")

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM admins") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                await add_admin(message.from_user.id, message.from_user.username)

    await state.update_data(current_parent_id=0, editor_mode=None)
    is_user_admin = await is_admin(message.from_user.id)
    text = "🛠 Admin Panel" if is_user_admin else "📚 Welcome to the Lectures Bot"
    await message.answer(text, reply_markup=await build_reply_keyboard(0, message.from_user.id))

@dp.message(F.text == "🏠 Main Menu")
async def go_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(current_parent_id=0, editor_mode=None)
    await message.answer("Main Menu", reply_markup=await build_reply_keyboard(0, message.from_user.id))

@dp.message(F.text == "🛑 Stop Editing")
async def stop_editing(message: types.Message, state: FSMContext):
    data = await state.get_data()
    parent_id = data.get("current_parent_id", 0)
    await state.update_data(editor_mode=None)
    await message.answer(
        "Editing stopped.",
        reply_markup=await build_reply_keyboard(parent_id, message.from_user.id, None)
    )

@dp.message(F.text == "🔙 Back")
async def go_back(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_id = data.get("current_parent_id", 0)
    editor_mode = data.get("editor_mode")

    if current_id == 0:
        await message.answer(
            "You are at the Main Menu.",
            reply_markup=await build_reply_keyboard(0, message.from_user.id, editor_mode)
        )
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT parent_id FROM buttons WHERE id = ?", (current_id,)
        ) as cursor:
            row = await cursor.fetchone()
            parent_id = row[0] if row else 0

    await state.update_data(current_parent_id=parent_id)
    await message.answer(
        "Going back...",
        reply_markup=await build_reply_keyboard(parent_id, message.from_user.id, editor_mode)
    )

# ===============================
# Editors
# ===============================
@dp.message(F.text == "⚙️ Buttons Editor")
async def btn_editor_mode(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.update_data(editor_mode="buttons")
    data = await state.get_data()
    parent_id = data.get("current_parent_id", 0)

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="➕ Add New Button Here",
            callback_data=f"add_btn_{parent_id}"
        )
    )

    await message.answer(
        "⚙️ Buttons Editor Mode Active",
        reply_markup=await build_reply_keyboard(parent_id, message.from_user.id, "buttons")
    )
    await message.answer(
        "Click any button to manage it or use the option below:",
        reply_markup=builder.as_markup()
    )

@dp.message(F.text == "✍️ Posts Editor")
async def post_editor_mode(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.update_data(editor_mode="posts")
    data = await state.get_data()
    parent_id = data.get("current_parent_id", 0)
    await message.answer(
        "✍️ Posts Editor Mode Active\nNavigate to the button where you want to add content.",
        reply_markup=await build_reply_keyboard(parent_id, message.from_user.id, "posts")
    )

@dp.message(F.text == "👥 Admins")
async def manage_admins_mode(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, username FROM admins") as cursor:
            admins = await cursor.fetchall()

    text = "Current Admins:\n"
    for uid, uname in admins:
        text += f"- {uname} ({uid})\n"

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="➕ Add Admin", callback_data="add_admin_prompt")
    )

    await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "add_admin_prompt")
async def add_admin_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.managing_admins)
    await callback.message.answer(
        "Send the User ID of the new admin or Forward a message from them."
    )

@dp.message(BotStates.managing_admins)
async def process_add_admin(message: types.Message, state: FSMContext):
    new_admin_id = None
    new_admin_name = "Unknown"

    if message.forward_from:
        new_admin_id = message.forward_from.id
        new_admin_name = (
            message.forward_from.username or message.forward_from.first_name
        )
    elif message.text and message.text.isdigit():
        new_admin_id = int(message.text)

    if new_admin_id:
        await add_admin(new_admin_id, new_admin_name)
        await message.answer(
            f"✅ Added {new_admin_name} ({new_admin_id}) as admin."
        )
        await state.set_state(None)
    else:
        await message.answer(
            "❌ Invalid input. Please send a User ID or forward a message."
        )

# ===============================
# Buttons & Content Logic
# ===============================
@dp.callback_query(F.data.startswith("add_btn_"))
async def add_btn_callback(callback: types.CallbackQuery, state: FSMContext):
    parent_id = int(callback.data.split("_")[2])
    await state.update_data(add_to_parent=parent_id)
    await state.set_state(BotStates.adding_button)
    await callback.message.answer(
        "Enter name for new button:",
        reply_markup=await build_reply_keyboard(parent_id, callback.from_user.id, "buttons")
    )

@dp.message(BotStates.adding_button)
async def process_add_btn(message: types.Message, state: FSMContext):
    if message.text in ["🛑 Stop Editing", "🔙 Back", "🏠 Main Menu"]:
        await state.set_state(None)
        await handle_all_text(message, state)
        return

    data = await state.get_data()
    parent_id = data.get("add_to_parent", 0)
    await add_button(message.text, parent_id)
    await message.answer(
        f"✅ Button '{message.text}' added!",
        reply_markup=await build_reply_keyboard(parent_id, message.from_user.id, "buttons")
    )
    await state.set_state(None)

@dp.message(F.text)
async def handle_all_text(message: types.Message, state: FSMContext):
    if message.text in [
        "⚙️ Buttons Editor", "✍️ Posts Editor", "👥 Admins",
        "🏠 Main Menu", "🔙 Back", "🛑 Stop Editing"
    ]:
        return

    data = await state.get_data()
    parent_id = data.get("current_parent_id", 0)
    editor_mode = data.get("editor_mode")

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM buttons WHERE name = ? AND parent_id = ?",
            (message.text, parent_id)
        ) as cursor:
            row = await cursor.fetchone()

    if not row:
        return

    btn_id = row[0]

    if editor_mode == "buttons":
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="⬆️", callback_data=f"move_up_{btn_id}"),
            types.InlineKeyboardButton(text="⬇️", callback_data=f"move_down_{btn_id}"),
            types.InlineKeyboardButton(text="⬅️", callback_data=f"move_left_{btn_id}"),
            types.InlineKeyboardButton(text="➡️", callback_data=f"move_right_{btn_id}")
        )
        builder.row(
            types.InlineKeyboardButton(text="📝 Rename", callback_data=f"rename_btn_{btn_id}"),
            types.InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_btn_{btn_id}")
        )
        builder.row(
            types.InlineKeyboardButton(text="➕ Add Sub-Button", callback_data=f"add_btn_{btn_id}")
        )
        await message.answer(
            f"Managing Button: {message.text}",
            reply_markup=builder.as_markup()
        )

    elif editor_mode == "posts":
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text="🗑 Clear Content", callback_data=f"clear_post_{btn_id}"
            )
        )
        builder.row(
            types.InlineKeyboardButton(
                text="➕ Add Content", callback_data=f"add_cont_{btn_id}"
            )
        )
        await message.answer(
            f"Managing Content for: {message.text}",
            reply_markup=builder.as_markup()
        )

    sub_buttons = await get_buttons(btn_id)
    if sub_buttons:
        await state.update_data(current_parent_id=btn_id)
        await message.answer(
            f"Entering {message.text}...",
            reply_markup=await build_reply_keyboard(btn_id, message.from_user.id, editor_mode)
        )
    elif not editor_mode:
        await show_content(message, btn_id)

async def show_content(message, btn_id):
    content = await get_content(btn_id)
    if not content:
        await message.answer("No content available here yet.")
        return

    for c_type, file_id, text, mg_id in content:
        if c_type == "text":
            await message.answer(text)
        elif c_type == "photo":
            await message.answer_photo(file_id)
        elif c_type == "video":
            await message.answer_video(file_id)
        elif c_type == "document":
            await message.answer_document(file_id)
        elif c_type == "audio":
            await message.answer_audio(file_id)
        elif c_type == "voice":
            await message.answer_voice(file_id)

# ===============================
# Start Bot
# ===============================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
