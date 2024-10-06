from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from datetime import datetime
from aiogram import types
from factories import *
from models import *

async def renderTask(callback, taskID):
    async with session() as s:
        task = (await s.execute(select(Task).where(Task.id == taskID))).scalar()

        message = f"Задача: {task.title}\n{task.text}\n\nСоздана @{task.started} в {datetime.fromtimestamp(task.timestamp_start).strftime("%d.%m.%Y %H:%M")}"
        kb = InlineKeyboardBuilder()

        r = await s.execute(select(User).where(User.id == callback.from_user.id))
        user = r.scalar()

        if task.statuscode == 0:
            message += f"\nЗадача еще не проверена модератором"
            if user.role >= 3:
                kb.row(types.InlineKeyboardButton(
                        text=f"Утвердить задачу",     
                        callback_data=TaskStatusFactory(id=task.id, statusEdit="moderate").pack()
                    ))
        elif task.statuscode == 1:
            message += f"\nЗадача еще не начата"
            kb.row(types.InlineKeyboardButton(
                        text=f"Начать задачу",     
                        callback_data=TaskStatusFactory(id=task.id, statusEdit="start").pack()
                ))
        elif task.statuscode == 2:
            message += f"\n\nЗадачу начал делать @{task.ended}"
            if task.ended == user.id:
                kb.row(
                    types.InlineKeyboardButton(
                        text=f"✅Завершить",     
                        callback_data=TaskStatusFactory(id=task.id, statusEdit="finish").pack()
                    ),
                    types.InlineKeyboardButton(
                        text=f"❌Перестать делать",
                        callback_data=TaskStatusFactory(id=task.id, statusEdit="giveup").pack()
                    )
                )
        elif task.statuscode == 3:
            message += f"\n\nЗадачу сделал @{task.ended} в {datetime.fromtimestamp(task.timestamp_end).strftime("%d.%m.%Y %H:%M")}"

        kb.row(
            types.InlineKeyboardButton(
                text = "◀️Назад",
                callback_data=QueueFactory(id=task.queueID).pack()
            )
        )
        await callback.message.delete()
        await callback.message.answer(message, reply_markup=kb.as_markup())

def getKeyboard(user):
    kb = [
        [types.KeyboardButton(text="Очереди")]
    ]

    if user.role >= 2:
        kb.append([
            types.KeyboardButton(text="Добавить задачу")
        ])
    if user.role >= 3:
        kb.append([
            types.KeyboardButton(text="Установить роль"), 
            types.KeyboardButton(text="Создать ссылку")
        ])
    if user.role == 4:
        kb.append([
            types.KeyboardButton(text="Создать очередь")
        ])
    
    return types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True
    )