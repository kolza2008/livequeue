import time
import asyncio
import logging
from uuid import uuid4
from config import *
from models import *
from render import *
from aiogram import F
from factories import *
from aiohttp import web
from sqlalchemy import select
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot, Dispatcher, types, BaseMiddleware
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)
# Объект бота
bot = Bot(token=BOT_TOKEN)
# Диспетчер
dp = Dispatcher(storage=MemoryStorage())

app = web.Application()

statuscodes = ["👀", "☑️", "🕘", "✅"]


class Middleware(BaseMiddleware):

    async def __call__(self, handler, event, data):
        async with session() as s:
            r = await s.execute(
                select(User).where(User.id == event.from_user.id))
            data["session"] = s
            data["user"] = r.scalar()
            res = await handler(event, data)
        return res


class NewTaskStates(StatesGroup):
    queue = State()
    title = State()
    text = State()


# Хэндлер на команду /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject, user: User,
                    session: AsyncSession):
    if user == None:
        invite = (await session.execute(
            select(Invite).where(Invite.text == command.args))).scalar()
        if invite == None:
            await message.answer("Недействительное приглашение")
        else:
            await session.delete(invite)
            user = User(id=message.from_user.id,
                        role=1,
                        name=message.from_user.username)
            session.add(user)
            await session.commit()
            await message.answer("Вы получили доступ к боту",
                                 reply_markup=getKeyboard(user))
    else:
        await message.answer("Вы уже получили приглашение в бота",
                             reply_markup=getKeyboard(user))


@dp.message(F.text == "Создать ссылку")
async def invite_generator(message: types.Message, user: User,
                           session: AsyncSession):
    if user != None and user.role >= 3:
        invite = Invite(text=uuid4().hex, author=user.id)
        session.add(invite)
        await session.commit()
        await message.answer(
            f"Ваша пригласительная ссылка: https://t.me/livequeuebot?start={invite.text}",
            reply_markup=getKeyboard(user))
    else:
        await message.answer("Вы не имеете доступа к этой команде",
                             reply_markup=getKeyboard(user))


@dp.message(F.text == "Очереди")
async def all_tasks_list(message: types.Message, user: User,
                         session: AsyncSession):
    if user != None and user.role >= 1:
        queues = (await session.execute(select(Queue))).scalars()

        kb = InlineKeyboardBuilder()
        for i in queues:
            kb.row(
                types.InlineKeyboardButton(
                    text=i.name, callback_data=QueueFactory(id=i.id).pack()))
        await message.answer("Список доступных очередей: ",
                             reply_markup=kb.as_markup())
    else:
        await message.answer("Вы не имеете доступа к этой команде",
                             reply_markup=getKeyboard(user))


@dp.message(F.text == "Добавить задачу")
async def new_task(message: types.Message, user: User, session: AsyncSession,
                   state: FSMContext):
    if user != None and user.role >= 2:
        kb = InlineKeyboardBuilder()
        for i in (await session.execute(select(Queue))).scalars():
            kb.row(
                types.InlineKeyboardButton(
                    text=i.name,
                    callback_data=QueueGetFactory(id=i.id).pack()))
        await state.set_state(NewTaskStates.queue)
        await message.answer("Хорошо",
                             reply_markup=types.ReplyKeyboardRemove())
        await message.answer("В какую очередь разместить задачу: ",
                             reply_markup=kb.as_markup())
    else:
        await message.answer("Вы не имеете доступа к этой команде",
                             reply_markup=getKeyboard(user))


@dp.callback_query(NewTaskStates.queue, QueueGetFactory.filter())
async def new_task_queue(callback: types.CallbackQuery,
                         callback_data: QueueGetFactory, state: FSMContext):
    await state.update_data(queue_id=callback_data.id)
    await state.set_state(NewTaskStates.title)
    await callback.message.answer("Напишите краткое название для задачи: ")


@dp.message(NewTaskStates.title)
async def new_task_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(NewTaskStates.text)
    await message.answer("Напишите описание для задачи: ")


@dp.message(NewTaskStates.text)
async def new_task_final(message: types.Message, user: User,
                         session: AsyncSession, state: FSMContext):
    await state.update_data(text=message.text)

    data = await state.get_data()
    task = Task(title=data['name'],
                text=data['text'],
                timestamp_start=time.time(),
                started=user.id,
                queueID=data['queue_id'])
    session.add(task)
    await session.commit()

    await state.clear()
    await message.answer("Задача добавлена в очередь",
                         reply_markup=getKeyboard(user))


@dp.callback_query(QueueFactory.filter())
async def get_data_by_queue(callback: types.CallbackQuery,
                            callback_data: QueueFactory):
    async with session() as s:
        queue = (await
                 s.execute(select(Queue).where(Queue.id == callback_data.id)
                           )).scalar()
    kb = InlineKeyboardBuilder()
    for i in queue.tasks:
        kb.row(
            types.InlineKeyboardButton(
                text=f"{statuscodes[i.statuscode]} - {i.title}",
                callback_data=TaskFactory(id=i.id).pack()))
    await callback.message.delete()
    await callback.message.answer(f"Задачи {queue.name}",
                                  reply_markup=kb.as_markup())


@dp.callback_query(TaskFactory.filter())
async def get_task(callback: types.CallbackQuery, callback_data: TaskFactory):
    await renderTask(callback, callback_data.id)


@dp.callback_query(TaskStatusFactory.filter())
async def get_task(callback: types.CallbackQuery,
                   callback_data: TaskStatusFactory):
    async with session() as s:
        r = await s.execute(
            select(User).where(User.id == callback.from_user.id))
        user = r.scalar()
        task = (await
                s.execute(select(Task).where(Task.id == callback_data.id)
                          )).scalar()

        if callback_data.statusEdit == "moderate":
            if user.role >= 3:
                task.statuscode = 1
                await s.commit()
                await renderTask(callback, callback_data.id)
            else:
                await callback.answer("Вы не имеете доступа к этому действию")
        elif callback_data.statusEdit == "start":
            if user.role >= 1:
                task.statuscode = 2
                task.ended = user.id
                await s.commit()
                await renderTask(callback, callback_data.id)
            else:
                await callback.answer("Вы не имеете доступа к этому действию")
        elif callback_data.statusEdit == "finish":
            if user.role >= 1 and task.ended == user.id:
                task.statuscode = 3
                task.timestamp_end = time.time()
                await s.commit()
                await renderTask(callback, callback_data.id)
            else:
                await callback.answer("Вы не имеете доступа к этому действию")
        elif callback_data.statusEdit == "giveup":
            if user.role >= 1 and task.ended == user.id:
                task.statuscode = 1
                task.ended = None
                await s.commit()
                await renderTask(callback, callback_data.id)
            else:
                await callback.answer("Вы не имеете доступа к этому действию")


async def on_startup(bot: Bot) -> None:
    # If you have a self-signed SSL certificate, then you will need to send a public
    # certificate to Telegram
    await bot.set_webhook(
        f"c4819cbc-c991-488c-9f88-91cff4b405a5-00-3c8znnhrwcnov.pike.replit.dev/webhook"
    )


# Запуск процесса поллинга новых апдейтов
async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    dp.message.middleware(Middleware())
    dp.startup.register(on_startup)

    # Create an instance of request handler,
    # aiogram has few implementations for different cases of usage
    # In this example we use SimpleRequestHandler which is designed to handle simple cases
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    # Register webhook handler on application
    webhook_requests_handler.register(app, path="/webhook")

    # Mount dispatcher startup and shutdown hooks to aiohttp application
    setup_application(app, dp, bot=bot)

    # And finally start webserver
    #await dp.start_polling(bot)
    await web._run_app(app, host="0.0.0.0", port=80)


if __name__ == "__main__":
    asyncio.run(main())
