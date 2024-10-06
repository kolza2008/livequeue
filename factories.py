from aiogram.filters.callback_data import CallbackData

class QueueFactory(CallbackData, prefix="queuedata"):
    id : int

class QueueGetFactory(CallbackData, prefix="queue2data"):
    id : int

class TaskFactory(CallbackData, prefix="taskdata"):
    id : int

class TaskStatusFactory(CallbackData, prefix="taskdata"):
    id : int
    statusEdit : str