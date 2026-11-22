"""Private Telegram homework tutor: parent dashboard, student hints, test switching."""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

import config
from storage import Storage
from tutor import Tutor, CodexBackend, OllamaBackend, MockBackend, OpenAIAPIBackend, EngineError

log = logging.getLogger('family_tutor')
Image.MAX_IMAGE_PIXELS = 20_000_000
DB: Storage
TUTOR: Tutor
AI_SEM = asyncio.Semaphore(2)
USER_LOCKS: dict[int, asyncio.Lock] = {}


def lock_for(user_id: int) -> asyncio.Lock:
    return USER_LOCKS.setdefault(user_id, asyncio.Lock())


def effective_role(user_id: int):
    return DB.mode(user_id)


def role_name(role: str | None):
    return {'parent': 'родитель', 'student': 'ученик', 'tester': 'тестировщик'}.get(role, 'не привязан')


async def say(update: Update, text: str, **kw):
    msg = update.effective_message
    for i in range(0, len(text), 3900):
        await msg.reply_text(text[i:i + 3900], **kw if i == 0 else {})


async def authorized(update: Update, role: str | None = None) -> bool:
    u, chat = update.effective_user, update.effective_chat
    if not u or not chat or chat.type != ChatType.PRIVATE:
        if update.effective_message:
            await say(update, 'Бот доступен только в личном чате, а не в группах.')
        return False
    current = effective_role(u.id)
    if not current:
        await say(update, 'Доступ закрыт. Попросите администратора выдать ваш секретный код привязки. Команда: /pair parent КОД или /pair student КОД или /pair tester КОД.')
        return False
    DB.remember_username(u.id, u.username or '')
    if role and current != role:
        await say(update, f'Эта команда доступна только роли «{role_name(role)}». Сейчас у вас роль «{role_name(current)}».')
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update):
        return
    user = DB.user(update.effective_user.id)
    mode = effective_role(update.effective_user.id)
    if user['role'] == 'tester':
        intro = 'Вы — тестировщик. /mode parent или /mode student позволяет проверить обе роли.\n'
    else:
        intro = ''
    if mode == 'parent':
        guide = ('/new Текст задания — создать черновик\nПришлите фото или допишите текст\n/publish — опубликовать\n'
                 '/tasks — список; /report НОМЕР — отчёт\n/evidence НОМЕР — фото решений\n'
                 '/approve НОМЕР — принять; /retry НОМЕР — попросить исправить\n'
                 '/delete НОМЕР — удалить задание со всеми материалами')
    else:
        guide = ('/tasks — получить список заданий\n/select НОМЕР — начать работу\n'
                 'Пришлите своё рассуждение, вопрос или фото решения\n'
                 '/done — передать работу на проверку родителю\n'
                 'Фото и сообщения сохраняются для проверки; отец видит отчёт и возможные попытки получить готовый ответ.')
    await say(update, f'📚 Семейный репетитор\nРоль: {role_name(mode)}\nTelegram ID: {update.effective_user.id}\n\n{intro}{guide}\n\nПравило: готовые ответы не выдаются; итог подтверждает родитель.')


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    u = update.effective_user
    user = DB.user(u.id)
    await say(update, f'Telegram ID: {u.id}\nТекущий ник: @{u.username or "отсутствует"}\nРоль: {user["role"] if user else "нет"}\nРежим: {effective_role(u.id) or "нет"}')


async def pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    if len(context.args) != 2:
        await say(update, 'Формат: /pair parent КОД (или student/tester). Не пересылайте код другим.')
        return
    role = context.args[0].strip().lower()
    code = context.args[1].strip()
    import hmac
    allowed = {'parent': config.PARENT_CODE, 'student': config.STUDENT_CODE, 'tester': config.TESTER_CODE}
    if role not in allowed or not hmac.compare_digest(code, allowed[role]):
        await say(update, 'Код или роль неверные.')
        return
    success, info = DB.register(update.effective_user.id, update.effective_user.username or '', role)
    await say(update, info + ('\n/start — открыть меню.' if success else ''))
    # Telegram still shows user-sent /pair in history; remind not to share this chat.


async def mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update):
        return
    u = DB.user(update.effective_user.id)
    if u['role'] != 'tester':
        await say(update, 'Переключение режимов доступно только закреплённому тестировщику.')
        return
    if not context.args or context.args[0] not in ('parent','student'):
        await say(update, 'Используйте /mode parent или /mode student.')
        return
    async with lock_for(update.effective_user.id):
        DB.set_mode(update.effective_user.id, context.args[0])
        await start(update, context)


async def new_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update, 'parent'):
        return
    title = ' '.join(context.args).strip()
    if len(title) < 3:
        await say(update, 'Укажите текст задания: /new Математика — упр. 158... Затем можно прислать фото.')
        return
    previous = DB.draft(update.effective_user.id)
    if previous:
        for image in DB.delete_task(previous['id']) or []:
            safe_unlink(image)
    id_ = DB.new_draft(update.effective_user.id, title)
    await say(update, f'Черновик #{id_} создан. Пришлите фото задания или ещё текст. Когда всё добавлено — /publish.')


async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update, 'parent'):
        return
    draft = DB.draft(update.effective_user.id)
    if not draft:
        await say(update, 'Нет черновика. Начните с /new ТЕКСТ.')
        return
    task_id = DB.publish(update.effective_user.id)
    await say(update, f'✅ Задание #{task_id} опубликовано. Ученик откроет его через /tasks.')
    student_id = DB.role_id('student')
    if student_id:
        try:
            await context.bot.send_message(student_id, f'📚 Новое домашнее задание #{task_id}: {draft["title"][:350]}\nОткрой /tasks, чтобы приступить.')
        except Exception:
            log.warning('Could not notify student; they must /start the bot first.')


async def task_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update):
        return
    items = DB.tasks()
    if not items:
        await say(update, 'Пока нет опубликованных заданий.')
        return
    ids = []
    for t in items[:20]:
        ids.append(f'#{t["id"]} — {t["title"].splitlines()[0][:90]}')
    reply = '📋 Домашние задания:\n' + '\n'.join(ids)
    if effective_role(update.effective_user.id) == 'student':
        buttons = [[InlineKeyboardButton(f'Начать #{x["id"]}', callback_data=f'select:{x["id"]}')]
                   for x in items[:10]]
        await say(update, reply, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await say(update, reply + '\n\nДля отчёта: /report НОМЕР')


async def show_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: int):
    t = DB.task(task_id)
    if not t or t['state'] != 'published':
        await say(update, 'Такого опубликованного задания нет.')
        return
    await say(update, f'Задание #{t["id"]}:\n{t["title"][:3500]}')
    for photo in DB.task_images(task_id):
        try:
            with open(photo, 'rb') as f:
                await update.effective_message.reply_photo(f)
        except OSError:
            log.warning('Task photo missing')


async def select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update, 'student'):
        return
    if not context.args or not context.args[0].isdigit():
        await say(update, 'Выбери задание командой /select НОМЕР.')
        return
    task_id = int(context.args[0])
    async with lock_for(update.effective_user.id):
        if not DB.select(update.effective_user.id, task_id):
            await say(update, 'Такого опубликованного задания нет.')
            return
        await show_task(update, context, task_id)
        await say(update, 'Что тебе уже известно из условия? Пришли первый шаг или фото своей попытки решения.')


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ''
    review = re.fullmatch(r'review:(approved|retry):(\d{1,9}):(\d{1,20})',data)
    if review:
        if not await authorized(update,'parent'):
            return
        state, tid, sid = review.group(1), int(review.group(2)), int(review.group(3))
        if sid not in (DB.role_id('student'), DB.role_id('tester')):
            await say(update,'Неизвестный ID ученика.')
            return
        if not DB.set_status(tid,sid,state):
            await say(update,'Задание не найдено.')
            return
        await say(update, f'Статус задания #{tid} обновлён: {state}.')
        try:
            await context.bot.send_message(sid, f'Родитель проверил задание #{tid}: '
                                           + ('✅ Принято.' if state=='approved' else '↩️ Требуется доработка.'))
        except Exception:
            pass
        return
    if not await authorized(update, 'student'):
        return
    match = re.fullmatch(r'select:(\d{1,9})', data)
    if not match:
        return
    tid = int(match.group(1))
    async with lock_for(update.effective_user.id):
        if DB.select(update.effective_user.id, tid):
            await show_task(update, context, tid)
            await say(update, 'С какого шага начнёшь?')
        else:
            await say(update, 'Задание недоступно.')


def pick_report_student(task_id: int, asked_id: int | None = None):
    if asked_id is not None:
        if asked_id not in (DB.role_id('student'), DB.role_id('tester')):
            return None
        return asked_id
    with DB.conn() as c:
        r = c.execute('''SELECT student_id FROM progress WHERE task_id=? ORDER BY updated_at DESC LIMIT 1''', (task_id,)).fetchone()
        return r['student_id'] if r else DB.role_id('student') or DB.role_id('tester')


def render_report(task_id: int, student_id: int) -> str:
    t = DB.task(task_id)
    if not t:
        return 'Задание не найдено.'
    s = DB.summary(task_id, student_id)
    status = {'working':'В работе', 'pending':'Ожидает проверки родителя', 'approved':'Подтверждено родителем',
              'retry':'Нужно доработать', 'not_started':'Ещё не начато'}.get(s['status'], s['status'])
    mastery = {'not_started':'нет данных', 'working':'в процессе', 'needs_review':'требуется уточнение',
               'demonstrated':'модель заметила самостоятельные объяснения (не доказательство)'}.get(s['mastery'], 'нет данных')
    flags = '\n'.join('• ' + f['flag_reason'] for f in s['flags']) if s['flags'] else 'Не обнаружено явных попыток. Это не гарантирует их отсутствие.'
    observations = '\n'.join('• ' + note for note in s['parent_notes']) if s['parent_notes'] else 'Пока нет наблюдений ИИ.'
    return (f'📊 Отчёт по заданию #{task_id}\n{t["title"].splitlines()[0][:200]}\n'
            f'Ученик ID: {student_id}\nСтатус: {status}\n'
            f'Сообщений ученика: {s["text_count"]}; фото решений: {s["photo_count"]}\n'
            f'Уровень по наблюдениям ИИ: {mastery}\n'
            f'Наблюдения по выполненным шагам (не оценки):\n{observations}\n'
            f'Заметок о возможных обходах: {s["flag_count"]}\n{flags}\n\n'
            f'⚠️ Бот не умеет достоверно распознавать ИИ-авторство по фото. '
            f'Попросите ученика устно объяснить 1–2 шага. Подтверждение работы — решение родителя.')


async def notify_parent(context: ContextTypes.DEFAULT_TYPE, content: str, student_id: int):
    parent = DB.role_id('parent')
    tester = DB.role_id('tester')
    dests = ([parent] if parent else [])
    if student_id == tester and tester not in dests:
        dests.append(tester)  # The test account can see both sides while simulating.
    for dest in dests:
        try:
            options = {}
            if content.startswith('📊'):
                match = re.search(r'заданию #(\d+)', content)
                if match:
                    tid = int(match.group(1))
                    options['reply_markup'] = InlineKeyboardMarkup([[
                        InlineKeyboardButton('✅ Принять',callback_data=f'review:approved:{tid}:{student_id}'),
                        InlineKeyboardButton('↩️ Доработать',callback_data=f'review:retry:{tid}:{student_id}')]])
            await context.bot.send_message(dest, content[:3900], **options)
        except Exception:
            log.warning('Cannot notify Telegram ID %s. User must first /start the bot.', dest)


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update, 'student'):
        return
    async with lock_for(update.effective_user.id):
        user_id = update.effective_user.id
        t = DB.selected(user_id)
        if not t:
            await say(update, 'Сначала выбери задание через /tasks.')
            return
        s = DB.summary(t['id'], user_id)
        if s['text_count'] + s['photo_count'] == 0:
            await say(update, 'Ты ещё не показывал свою работу. Пришли хотя бы один собственный шаг или фото решения.')
            return
        DB.set_status(t['id'], user_id, 'pending')
        await say(update, '📨 Работа передана родителю на проверку. Это пока не означает, что она принята.')
        await notify_parent(context, render_report(t['id'], user_id), user_id)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update, 'parent'):
        return
    if not context.args or not context.args[0].isdigit():
        await say(update, 'Формат: /report НОМЕР [TELEGRAM_ID], например /report 3')
        return
    tid = int(context.args[0])
    requested = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else None
    sid = pick_report_student(tid, requested)
    if sid is None:
        await say(update, 'Нет разрешённой записи ученика или указан неверный Telegram ID.')
        return
    await say(update, render_report(tid,sid))


async def status_change(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str):
    if not await authorized(update,'parent'):
        return
    if not context.args or not context.args[0].isdigit():
        await say(update, f'Формат: /{"approve" if status=="approved" else "retry"} НОМЕР [TELEGRAM_ID]')
        return
    tid = int(context.args[0])
    req = int(context.args[1]) if len(context.args)>1 and context.args[1].isdigit() else None
    sid = pick_report_student(tid, req)
    if sid is None or not DB.set_status(tid,sid,status):
        await say(update, 'Задание или ученик не найден.')
        return
    await say(update, f'Статус задания #{tid} обновлён: {status}.')
    try:
        await context.bot.send_message(sid, f'Родитель обновил статус задания #{tid}: '
                                           + ('✅ Принято.' if status=='approved' else '↩️ Нужно доработать. Напиши, что не получилось.'))
    except Exception:
        pass


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await status_change(update, context, 'approved')


async def retry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await status_change(update, context, 'retry')


async def evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update,'parent'):
        return
    if not context.args or not context.args[0].isdigit():
        await say(update, 'Формат: /evidence НОМЕР')
        return
    tid = int(context.args[0]); sid = pick_report_student(tid)
    if not sid:
        await say(update, 'Нет работ ученика.')
        return
    photos = DB.recent_photos(tid,sid)
    if not photos:
        await say(update, 'Фото решений пока нет.')
        return
    for path in photos:
        try:
            with open(path, 'rb') as photo:
                await update.effective_message.reply_photo(photo)
        except OSError:
            await say(update, 'Одно из старых фото было удалено по сроку хранения.')


def safe_unlink(path: str):
    root = config.UPLOAD_DIR.resolve()
    target = Path(path).resolve()
    if target.is_relative_to(root):
        target.unlink(missing_ok=True)


async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update, 'parent'):
        return
    if not context.args or not context.args[0].isdigit():
        await say(update, 'Формат: /delete НОМЕР — удалить задание, всю переписку и фото (без восстановления).')
        return
    tid = int(context.args[0])
    paths = DB.delete_task(tid)
    if paths is None:
        await say(update, 'Задание не найдено.')
        return
    for path in paths:
        safe_unlink(path)
    await say(update, f'Удалено задание #{tid}, его история и сохранённые фотографии.')


async def photo_to_jpeg(update: Update) -> str:
    message = update.effective_message
    if message.photo:
        item = message.photo[-1]
    elif message.document and message.document.mime_type in ('image/jpeg','image/png','image/webp'):
        item = message.document
    else:
        raise ValueError('Пришлите обычное фото или файл JPG/PNG/WEBP.')
    if item.file_size and item.file_size > 8_000_000:
        raise ValueError('Фото больше 8 МБ. Уменьши файл и попробуй ещё раз.')
    tgfile = await item.get_file()
    tmp = config.UPLOAD_DIR / (uuid.uuid4().hex + '.tmp')
    dest = config.UPLOAD_DIR / (uuid.uuid4().hex + '.jpg')
    try:
        await tgfile.download_to_drive(custom_path=tmp)
        if tmp.stat().st_size > 8_000_000:
            raise ValueError('Фото больше 8 МБ.')
        with Image.open(tmp) as im:
            if im.width * im.height > 16_000_000:
                raise ValueError('Разрешение фото слишком большое. Уменьши его перед отправкой.')
            im.load()
            normalized = ImageOps.exif_transpose(im)
            normalized.thumbnail((1800,1800),Image.Resampling.LANCZOS)
            normalized = normalized.convert('RGB')
            normalized.save(dest,'JPEG',quality=82,optimize=True)
        return str(dest.resolve())
    except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('Этот файл не похож на безопасное изображение.') from exc
    finally:
        tmp.unlink(missing_ok=True)


async def text_or_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update):
        return
    await _handle_message(update, context)


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = update.effective_message
    role = effective_role(uid)
    content = (msg.text or msg.caption or '').strip()[:2000]
    has_image = bool(msg.photo or (msg.document and msg.document.mime_type in ('image/jpeg','image/png','image/webp')))
    if not content and not has_image:
        await say(update, 'Поддерживаются текст и фотографии JPG/PNG/WEBP.')
        return
    async with lock_for(uid):
        image_path = None
        if has_image:
            try:
                image_path = await photo_to_jpeg(update)
            except (ValueError, OSError) as exc:
                await say(update, str(exc))
                return
        if role == 'parent':
            draft = DB.draft(uid)
            if not draft:
                if image_path:
                    safe_unlink(image_path)
                await say(update, 'Сначала создайте черновик: /new ТЕКСТ ЗАДАНИЯ.')
                return
            if content:
                DB.append_draft_text(uid, content)
            if image_path and not DB.add_draft_photo(uid,image_path):
                safe_unlink(image_path)
                await say(update, 'В черновике уже максимум 5 фото. Создайте новый черновик или опубликуйте этот.')
                return
            await say(update, 'Добавлено в черновик. Для отправки ученику используйте /publish.')
            return
        task = DB.selected(uid)
        if not task or task['state'] != 'published':
            if image_path:
                safe_unlink(image_path)
            await say(update, 'Сначала выбери задание: /tasks, затем /select НОМЕР.')
            return
        if len(content) > 1950:
            await say(update, 'Сообщение слишком длинное. Опиши один шаг короче.')
            if image_path:
                safe_unlink(image_path)
            return
        if config.BACKEND in ('codex', 'openai_api', 'ollama') and DB.daily_tutor_turns(uid) >= config.MAX_DAILY_TURNS:
            if image_path:
                safe_unlink(image_path)
            await say(update,f'Сегодня исчерпан лимит: {config.MAX_DAILY_TURNS} обращений к репетитору. '
                             'Лимит защищает семейную подписку от чрезмерных запросов. '
                             'Можно продолжить завтра или переключить сервер на локальную модель.')
            return
        history = DB.recent(task['id'],uid,limit=24)
        student_note = content or 'Ученик прислал фото собственного задания/решения. Проверь ход рассуждений; не выдавай решение.'
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            async with AI_SEM:
                earlier = DB.recent_photos(task['id'],uid,count=1)
                image_context = ([image_path] if image_path else []) + [p for p in earlier if p != image_path]
                decision = await asyncio.to_thread(TUTOR.respond, task, history, student_note,
                    DB.task_images(task['id']), image_context)
        except EngineError as exc:
            DB.log(task['id'],uid,'student','photo' if image_path else 'text',content,image_path)
            log.warning('AI engine unavailable: %s', exc)
            await say(update, f'⚠️ Нейросеть сейчас не проверила работу: {exc}\nПопробуй позже. Результат не засчитан как проверенный.')
            return
        except Exception:
            DB.log(task['id'],uid,'student','photo' if image_path else 'text',content,image_path)
            log.exception('Unexpected inference failure')
            await say(update, '⚠️ Ошибка проверки нейросетью. Работа сохранена, но не проверена. Попробуй позже.')
            return
        current = DB.summary(task['id'],uid)
        # No automatic mastery claims based on a single or a couple of messages.
        if decision.mastery == 'demonstrated' and current['text_count'] + current['photo_count'] < 3:
            decision.mastery = 'needs_review'
        prev_flags = current['flag_count']
        DB.log(task['id'],uid,'student','photo' if image_path else 'text',content,image_path,
               flag=decision.flag,flag_reason=decision.flag_reason)
        DB.log(task['id'],uid,'bot','text',decision.reply,mastery=decision.mastery,
               parent_note=decision.parent_note)
        await say(update, decision.reply)
        if decision.flag != 'none' and prev_flags == 0:
            await notify_parent(context,
                f'⚠️ Возможная попытка обхода в задании #{task["id"]} от ID {uid}. '
                f'Это не доказательство обмана. Наблюдение: {decision.flag_reason[:250]}\n'
                f'/report {task["id"]}', uid)


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update):
        return
    u = DB.user(update.effective_user.id)
    if u['role'] not in ('parent', 'tester'):
        await say(update, 'Диагностика доступна администратору.')
        return
    with DB.conn() as c:
        db = c.execute('PRAGMA quick_check').fetchone()[0]
    await say(update, f'🩺 Family Tutor\nИИ: {config.BACKEND}\nSQLite: {db}\n'
                      f'Лимит обращений за сутки: {config.MAX_DAILY_TURNS}\n'
                      'Для проверки авторизации Codex на Ubuntu: sudo -Hu tutorbot codex login status')


async def command_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update):
        return
    await say(update, 'Неизвестная команда. /start — доступные действия.')


async def errors(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error('Unhandled telegram error', exc_info=context.error)
    if isinstance(update,Update) and update.effective_message:
        try:
            await say(update, 'Произошла техническая ошибка. Попробуйте команду ещё раз.')
        except Exception:
            pass


async def housekeeping(app: Application):
    while True:
        try:
            n, paths = DB.purge_old_events(30)
            for path in paths:
                safe_unlink(path)
            if n:
                log.info('Removed %d old event records.', n)
        except Exception:
            log.exception('Retention cleanup failed')
        await asyncio.sleep(86400)


async def post_init(app: Application):
    app.bot_data['cleanup_task'] = asyncio.create_task(housekeeping(app))
    info = await app.bot.get_me()
    log.info('Telegram bot @%s started.', info.username)


async def post_shutdown(app: Application):
    task = app.bot_data.get('cleanup_task')
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def main():
    global DB, TUTOR
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    config.validate()
    DB = Storage(config.DB_FILE)
    if config.BACKEND == 'codex':
        backend = CodexBackend(model=config.MODEL)
    elif config.BACKEND == 'openai_api':
        backend = OpenAIAPIBackend(api_key=config.OPENAI_API_KEY, model=config.API_MODEL)
    elif config.BACKEND == 'ollama':
        backend = OllamaBackend(model=config.OLLAMA_MODEL)
    else:
        backend = MockBackend()
    TUTOR = Tutor(backend)
    log.info('Backend: %s. Student content is private; no secrets are logged.',config.BACKEND)
    app = (Application.builder().token(config.BOT_TOKEN).concurrent_updates(4)
           .post_init(post_init).post_shutdown(post_shutdown).build())
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', start))
    app.add_handler(CommandHandler('whoami', whoami))
    app.add_handler(CommandHandler('health', health))
    app.add_handler(CommandHandler('pair', pair))
    app.add_handler(CommandHandler('mode', mode))
    app.add_handler(CommandHandler('new', new_task))
    app.add_handler(CommandHandler('publish', publish))
    app.add_handler(CommandHandler('tasks', task_list))
    app.add_handler(CommandHandler('select', select))
    app.add_handler(CommandHandler('done', done))
    app.add_handler(CommandHandler('report', report))
    app.add_handler(CommandHandler('evidence', evidence))
    app.add_handler(CommandHandler('approve', approve))
    app.add_handler(CommandHandler('retry', retry))
    app.add_handler(CommandHandler('delete', delete_task))
    app.add_handler(CallbackQueryHandler(callbacks, pattern=r'^(select:\d+|review:(?:approved|retry):\d+:\d+)$'))
    app.add_handler(MessageHandler((filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.Document.IMAGE, text_or_photo))
    app.add_handler(MessageHandler(filters.COMMAND,command_unknown))
    app.add_error_handler(errors)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == '__main__':
    main()
