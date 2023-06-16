import logging
import io
import csv
import os
import sqlite3

from config import *

from aiogram import Bot, Dispatcher, types
from aiogram import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.filters.state import State, StatesGroup


API_TOKEN = TOKEN


bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


logging.basicConfig(level=logging.INFO)


conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Создание таблицы для хранения ответов
cursor.execute('''
    CREATE TABLE IF NOT EXISTS registration (
        user_id INTEGER PRIMARY KEY,
        question1 TEXT ,
        question2 TEXT,
        question3 TEXT
        )
''')
conn.commit()

class RegistrationStates(StatesGroup):
    question1 = State()
    question2 = State()
    question3 = State()


class AddStateFSM(StatesGroup):
    enter_user_id = State()

name_mapping = {}  # Словарь для хранения соответствия идентификаторов и имен администраторов


class RegistrationAdmin(StatesGroup):
    admin_name = State()

@dp.message_handler(Command('start'))
async def start_command(message: types.Message):
    if check_admins(message.from_user.id):
        if message.from_user.id not in name_mapping:
            await message.answer("Вы администратор. Доступ к /csv разрешён, но перед этим представьтесь.")
            await RegistrationAdmin.admin_name.set()
        else:
            await message.answer("Вы уже зарегистрированы в боте.")
    else:
        # Создаем меню с кнопкой "Начать регистрацию"
        start_registration_button = InlineKeyboardButton("Начать регистрацию", callback_data='start_registration')
        start_registration_menu = InlineKeyboardMarkup().add(start_registration_button)

        # Отправляем сообщение с кнопкой
        await message.answer("Привет, это тест бот для INEX.", reply_markup=start_registration_menu)


@dp.message_handler(state=RegistrationAdmin.admin_name)
async def process_admin_name(message: types.Message, state: FSMContext):
    admin_id = message.from_user.id
    name_mapping[admin_id] = message.text

    await state.finish()
    await message.answer("Спасибо! Ваше имя зарегистрировано.")


@dp.message_handler(Command('admins'))
async def admins_command(message: types.Message):
    if check_admins(message.from_user.id):
        response_message = "Список администраторов:\n"
        for admin_id in ADMIN:
            name = name_mapping.get(admin_id)
            if name:
                response_message += f"- {admin_id}: {name}\n"
            else:
                response_message += f"- {admin_id}: не зарегистрирован в боте\n"

        await message.answer(response_message)
    else:
        await message.answer("У вас нет доступа к этой команде.")


@dp.callback_query_handler(lambda query: query.data == 'start_registration')
async def start_registration_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()

    # Устанавливаем начальное состояние
    await RegistrationStates.question1.set()

    # Отправляем первый вопрос
    await bot.send_message(callback_query.from_user.id, "Давайте познакомимся, введите ваше имя")


@dp.message_handler(state=RegistrationStates.question1)
async def process_question1(message: types.Message, state: FSMContext):
    # Сохраняем ответ на первый вопрос
    answer = message.text

    # Сохраняем ответ в базу данных
    cursor.execute("INSERT INTO registration (user_id, question1) VALUES (?, ?)", (message.from_user.id, answer))
    conn.commit()

    # Переходим ко второму вопросу
    await RegistrationStates.next()
    await message.answer("Введите вашу фамилию")
@dp.message_handler(state=RegistrationStates.question2)
async def process_question2(message: types.Message, state: FSMContext):
    # Сохраняем ответ на второй вопрос
    answer = message.text

    # Сохраняем ответ в базу данных
    cursor.execute("UPDATE registration SET question2 = ? WHERE user_id = ?", (answer, message.from_user.id))
    conn.commit()

    await RegistrationStates.next()
    await message.answer("Введите ваш email")


@dp.message_handler(state=RegistrationStates.question3)
async def process_question3(message: types.Message, state: FSMContext):

    answer = message.text

    cursor.execute("UPDATE registration SET question3 = ? WHERE user_id = ?", (answer, message.from_user.id))
    conn.commit()

    # Завершаем регистрацию
    await state.finish()
    await message.answer("Регистрация завершена. Спасибо!")

    # Закрываем подключение к базе данных
    conn.close()


def check_admins(user_id):
    admin_ids = ADMIN  # Список user_id бояр
    return user_id in admin_ids


@dp.message_handler(commands=['csv'])
async def send_csv_file(message: types.Message):
    # Плебей не проходит в клуб CSV, если он не в списке
    if not check_admins(message.from_user.id):
        await message.answer("Вы не являетесь администратором.")
        return

    # Подключаемся к бд
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Получаем данные из базы данных
    cursor.execute("SELECT * FROM registration")
    data = cursor.fetchall()

    # Создаем CSV-файл
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(('user_id', 'question1', 'question2', 'question3'))
    for row in data:
        writer.writerow(row)

    # Отправляем CSV-файл в сообщении
    output.seek(0)  # переводим указатель на начало файла
    filename = "users.csv"
    with open(filename, "w", newline="") as file:
        file.write(output.getvalue())
    await message.answer_document(open(filename, "rb"))
    os.remove(filename)

    # Закрываем подключение к базе данных
    conn.close()



# Функция для добавления бояр не через разраба, чтобы меня как всея господа бота не тревожили по пустякам
@dp.message_handler(Command('add'))
async def add_command_handler(message: Message):
    user_id = message.from_user.id

    # Проверка пользователя в списке бояр ADMIN
    if user_id not in ADMIN:
        await message.answer("У вас нет доступа к данной команде.")
        return

    await message.answer("Введите user_id пользователя (Можно получить в @getmyid_bot):")
    await AddStateFSM.enter_user_id.set()


@dp.message_handler(state=AddStateFSM.enter_user_id)
async def add_user_id_handler(message: Message, state: FSMContext):
    user_id = message.text

    # Проверка введенного user_id, не знаю работает ли
    if not user_id.isdigit():
        await message.answer("Некорректный user_id. Попробуйте еще раз.")
        return

    user_id = int(user_id)

    # Проверка user_id в списке бояр ADMIN
    if user_id in ADMIN:
        await message.answer(f"Пользователь с user_id {user_id} уже присутствует в списке администраторов.")
    else:
        ADMIN.append(user_id)
        await message.answer(f"Пользователь с user_id {user_id} добавлен в список администраторов.")

    await state.finish()




if __name__ == '__main__':
    executor.start_polling(dp, skip_updates= True)
