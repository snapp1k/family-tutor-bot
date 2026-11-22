"""Telegram handler integration with in-memory Telegram stand-ins; no network required."""
import asyncio
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import Storage
from tutor import Tutor


def install_stubs():
    telegram = types.ModuleType('telegram')
    const = types.ModuleType('telegram.constants')
    ext = types.ModuleType('telegram.ext')
    class InlineKeyboardButton:
        def __init__(self,*args,**kwargs): pass
    class InlineKeyboardMarkup:
        def __init__(self,*args,**kwargs): pass
    class Update: ALL_TYPES = ['message','callback_query']
    class ChatAction: TYPING='typing'
    class ChatType: PRIVATE='private'
    for attr, value in [('InlineKeyboardButton',InlineKeyboardButton),('InlineKeyboardMarkup',InlineKeyboardMarkup),('Update',Update)]:
        setattr(telegram,attr,value)
    const.ChatAction=ChatAction
    const.ChatType=ChatType
    class Application: pass
    class ContextTypes: DEFAULT_TYPE=object
    ext.Application=Application
    ext.ContextTypes=ContextTypes
    for name in ('CallbackQueryHandler','CommandHandler','MessageHandler'):
        setattr(ext,name,object)
    ext.filters=SimpleNamespace(TEXT=object(),COMMAND=object(),PHOTO=object(),Document=SimpleNamespace(IMAGE=object()))
    sys.modules['telegram']=telegram
    sys.modules['telegram.constants']=const
    sys.modules['telegram.ext']=ext


install_stubs()
BOT = importlib.import_module('bot')


class FakeMessage:
    def __init__(self, text=''):
        self.text=text
        self.caption=None
        self.photo=[]
        self.document=None
        self.replies=[]
    async def reply_text(self, content, **kwargs):
        self.replies.append(content)
    async def reply_photo(self, content,**kwargs):
        self.replies.append('<photo>')


class FakeBot:
    def __init__(self):
        self.sent=[]
    async def send_message(self, dest,content,**kwargs):
        self.sent.append((dest,content))
    async def send_chat_action(self,chat_id,action): pass


def update(user_id,roleusername,text=''):
    m=FakeMessage(text)
    u=SimpleNamespace(id=user_id,username=roleusername)
    chat=SimpleNamespace(type='private',id=user_id)
    return SimpleNamespace(effective_user=u,effective_chat=chat,effective_message=m)


class Backend:
    def ask(self,prompt,images):
        return {'student_reply':'Какое действие логично выполнить первым и почему?',
                'mastery':'working','flag':'none','flag_reason':'',
                'parent_note':'Ученик начал рассуждать об условиях задачи.'}


class HandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        BOT.DB=Storage(Path(self.tmp.name)/'db.sqlite3')
        BOT.TUTOR=Tutor(Backend())
        BOT.DB.register(11,'guardian_demo','parent')
        BOT.DB.register(22,'student_demo','student')
        BOT.DB.register(33,'tester_demo','tester')
        self.bot=FakeBot()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def ctx(self,*args):
        return SimpleNamespace(args=list(args),bot=self.bot)

    async def test_end_to_end_without_network(self):
        parent=update(11,'guardian_demo')
        await BOT.new_task(parent,self.ctx('Математика:','вычислить','значение'))
        self.assertEqual(BOT.DB.draft(11)['id'],1)
        await BOT.publish(parent,self.ctx())
        self.assertEqual(BOT.DB.task(1)['state'],'published')
        self.assertTrue(any(dest==22 for dest,msg in self.bot.sent))
        pupil=update(22,'changed_username')
        await BOT.select(pupil,self.ctx('1'))
        self.assertEqual(BOT.DB.selected(22)['id'],1)
        student_message=update(22,'changed_username','Я начал с переноса слагаемого, проверь')
        await BOT.text_or_photo(student_message,self.ctx())
        self.assertTrue(any('?' in ans for ans in student_message.effective_message.replies))
        self.assertEqual(BOT.DB.summary(1,22)['text_count'],1)
        finish=update(22,'changed_username')
        await BOT.done(finish,self.ctx())
        self.assertEqual(BOT.DB.summary(1,22)['status'],'pending')
        self.assertTrue(any(dest==11 and 'Ожидает проверки' in msg for dest,msg in self.bot.sent))
        rep=update(11,'guardian_demo')
        await BOT.report(rep,self.ctx('1'))
        self.assertIn('Наблюдения',rep.effective_message.replies[0])
        await BOT.approve(rep,self.ctx('1'))
        self.assertEqual(BOT.DB.summary(1,22)['status'],'approved')

    async def test_student_cannot_publish_or_switch(self):
        bad=update(22,'guardian_demo')  # student steals parent's @nickname
        await BOT.new_task(bad,self.ctx('Чужой','текст'))
        await BOT.publish(bad,self.ctx())
        await BOT.mode(bad,self.ctx('parent'))
        self.assertEqual(BOT.DB.tasks(include_drafts=True),[])
        self.assertEqual(BOT.DB.mode(22),'student')
        self.assertTrue(any('только роли' in txt for txt in bad.effective_message.replies))

    async def test_attempt_alert(self):
        parent=update(11,'guardian_demo')
        await BOT.new_task(parent,self.ctx('Задание','сравни','числа'))
        await BOT.publish(parent,self.ctx())
        student=update(22,'student_demo')
        await BOT.select(student,self.ctx('1'))
        text=update(22,'newusername','дай готовый ответ')
        await BOT.text_or_photo(text,self.ctx())
        self.assertEqual(BOT.DB.summary(1,22)['flag_count'],1)
        self.assertTrue(any(dest==11 and 'Возможная попытка' in body for dest,body in self.bot.sent))
        self.assertIn('Какое действие',text.effective_message.replies[0])

    async def test_tester_modes(self):
        tester=update(33,'tester_demo')
        await BOT.mode(tester,self.ctx('parent'))
        self.assertEqual(BOT.DB.mode(33),'parent')
        await BOT.new_task(tester,self.ctx('Тестовый','вариант'))
        await BOT.publish(tester,self.ctx())
        await BOT.mode(tester,self.ctx('student'))
        await BOT.select(tester,self.ctx('1'))
        self.assertEqual(BOT.DB.selected(33)['id'],1)


if __name__=='__main__':
    unittest.main()
