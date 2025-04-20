import os
import logging
import asyncio
import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC
from mutagen.flac import FLAC, Picture
from mutagen.m4a import M4A
from mutagen.wave import WAVE
from PIL import Image
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(_name_)

bot = Bot(token=os.getenv("7847591550:AAGbjjwj0tiVqqILuM4ug7Z07_bGpe6IFJo"))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class AudioState(StatesGroup):
    WAIT_FILES = State()
    PROCESSING = State()

# Загрузка стандартной обложки
with open("avatarka.jpg", "rb") as f:
    DEFAULT_COVER = f.read()

async def cleanup_metadata(file_data: bytes, filename: str) -> bytes:
    """Очищает метаданные и добавляет обложку"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file_data)
        tmp_path = tmp.name

    try:
        if filename.lower().endswith('.mp3'):
            audio = MP3(tmp_path, ID3=ID3)
            # Сохраняем оригинальные название и исполнителя
            title = audio.get("TIT2", [""])[0]
            artist = audio.get("TPE1", [""])[0]
            
            # Очищаем все теги
            audio.delete()
            audio.add_tags()
            
            # Устанавливаем только нужные теги
            if title:
                audio["TIT2"] = TIT2(encoding=3, text=title)
            if artist:
                audio["TPE1"] = TPE1(encoding=3, text=artist)
            
            audio["COMM"] = COMM(encoding=3, text="https://t.me/danixsik")
            audio["APIC"] = APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=DEFAULT_COVER
            )
            audio.save()

        elif filename.lower().endswith('.flac'):
            audio = FLAC(tmp_path)
            title = audio.get("title", [""])[0]
            artist = audio.get("artist", [""])[0]
            
            # Очищаем теги
            audio.clear()
            
            if title:
                audio["title"] = title
            if artist:
                audio["artist"] = artist
            
            audio["comment"] = "https://t.me/danixsik"
            
            picture = Picture()
            picture.type = 3
            picture.mime = "image/jpeg"
            picture.data = DEFAULT_COVER
            audio.add_picture(picture)
            audio.save()

        elif filename.lower().endswith(('.m4a', '.mp4')):
            audio = M4A(tmp_path)
            title = audio.get("\xa9nam", [""])[0]
            artist = audio.get("\xa9ART", [""])[0]
            
            audio.clear()
            
            if title:
                audio["\xa9nam"] = title
            if artist:
                audio["\xa9ART"] = artist
            
            audio["\xa9cmt"] = "https://t.me/danixsik"
            audio["covr"] = [MP4Cover(DEFAULT_COVER)]
            audio.save()

        elif filename.lower().endswith('.wav'):
            audio = WAVE(tmp_path)
            # WAV обычно не поддерживает метаданные, пропускаем

        # Читаем обработанный файл
        with open(tmp_path, "rb") as f:
            return f.read()

    finally:
        os.unlink(tmp_path)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await AudioState.WAIT_FILES.set()
    await message.answer(
        "🎵 Отправьте до 10 аудиофайлов для обработки\n"
        "Форматы: MP3, M4A, FLAC, WAV",
        reply_markup=get_main_menu()
    )

def get_main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✏ Изменить название", callback_data="edit_title"),
        InlineKeyboardButton("👤 Изменить автора", callback_data="edit_artist"),
        InlineKeyboardButton("🖼 Изменить обложку", callback_data="edit_cover"),
        InlineKeyboardButton("♻ Сбросить изменения", callback_data="reset"),
        InlineKeyboardButton("💾 Применить пресет", callback_data="apply_preset")
    )
    return keyboard

@dp.message_handler(content_types=types.ContentType.AUDIO, state=AudioState.WAIT_FILES)
async def handle_audio(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if 'files' not in data:
            data['files'] = []
        
        if len(data['files']) >= 10:
            await message.answer("ℹ Максимум 10 файлов за раз")
            return
        
        data['files'].append((message.audio.file_id, message.audio.file_name))
        
        if len(data['files']) == 1:
            await message.answer(f"✅ Файл получен. Можно отправить еще {9 - len(data['files'])}")
        else:
            await message.answer(f"✅ Файлов получено: {len(data['files'])}/10")

@dp.message_handler(commands=['process'], state=AudioState.WAIT_FILES)
async def process_files(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if 'files' not in data or not data['files']:
            await message.answer("❌ Нет файлов для обработки")
            return
        
        await AudioState.PROCESSING.set()
        await message.answer("🔄 Начинаю обработку...")
        
        processed_count = 0
        for file_id, filename in data['files']:
            try:
                file = await bot.get_file(file_id)
                file_data = await bot.download_file(file.file_path)
                
                processed_data = await cleanup_metadata(file_data.read(), filename)
                
                await message.reply_audio(
                    audio=types.InputFile(io.BytesIO(processed_data), filename=filename)
                )
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                await message.answer(f"❌ Ошибка при обработке файла {filename}")
        
        await message.answer(f"🎵 Обработано файлов: {processed_count}/{len(data['files'])}")
        await AudioState.WAIT_FILES.set()
        data['files'] = []

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)