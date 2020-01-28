import sqlite3
import requests
import os
import subprocess
import time


import cv2
import telebot


token = '949972967:AAGuKN-d2c2QWHMfSGXDN0_xNr-ZmCne0-g'


bot = telebot.TeleBot(token, threaded=False) # убираем многопоточность чтоб не падал


name_db = 'msg_file.db'
cur_dir = os.getcwd()
path_db = os.path.join(cur_dir, name_db)


# проверка на существование базы данных и ее создание
if not os.path.exists(path_db):
    try:
        conn = sqlite3.connect(path_db)
        cursor = conn.cursor()
        cursor.executescript("""CREATE TABLE msg (
                                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                                msg BLOB NOT NULL,
                                id_user INTEGER NOT NULL,
                                created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()

    except sqlite3.Error as e:
        print('База данных уже создана ' + str(e))


def conv(src_file_name):
    """конвертирует все аудиосообщения в формат wav с частотой дискретизации 16kHz"""
    program = "ffmpeg -i " + src_file_name + " -acodec pcm_s16le -ac 1 -ar 16000 " + src_file_name + '_to_wav.wav'
    # тут просто передаем виртальной машине, на которой крутится скрипт команду для конвертации
    # предварительно на нее нужно накатить FFmpeg если нет
    process = subprocess.Popen(program, shell=True)


def photo_detect(image):
    """определяет есть ли лицо на отправляемых фотографиях или нет, возвращает количество найденных"""
    image_path = image
    face_cascade = cv2.CascadeClassifier('/home/supertema/.local/lib/python3.7/site-packages/cv2/data/haarcascade_frontalface_default.xml')
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor= 1.1,
        minNeighbors= 7, # чем выше значение, тем точнее определяет (требует больше ресурсов)
        minSize=(15, 15)
    )
    faces_detected = "Лиц обнаружено: " + format(len(faces))
    return faces_detected


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, "Привет! Отправьте мне голосовое сообщение или фотографию. Если на фото будут найдены лица - фото сохранится в базу данных")


@bot.message_handler(content_types=['photo'])
def photo_msg_in_directory(message):
    """сохраняет фото в БД если есть лицо"""
    id_user = message.from_user.id
    file_info = bot.get_file(message.photo[1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    src = os.getcwd() + message.photo[1].file_id + '.jpg'
    with open(src, 'wb') as new_file:
        new_file.write(downloaded_file)
    photo_detect(src)
    s = photo_detect(src)
    print(s)
    if int(s[-1]) == 0:
        bot.reply_to(message, s +' - не сохранено')
        os.remove(src)
        print('Не сохранено')
    else:
        con = sqlite3.connect('msg_file.db')
        cursor = con.cursor()
        cursor.execute("INSERT INTO msg (msg, id_user) VALUES (?, ?)", (downloaded_file, id_user))
        con.commit()
        con.close()
        bot.reply_to(message, s +' - ваше фото сохранено в базу данных')
        print('Сохранено')
        os.remove(src)


@bot.message_handler(content_types=['voice'])
def audio_msg_in_directory(message):
    """отправляет пользователю сконвертированное голосовое сообщение"""
    id_user = message.from_user.id
    file_info = bot.get_file(message.voice.file_id)
    file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(token, file_info.file_path))
    src = os.getcwd() + message.voice.file_id
    with open(src, 'wb') as new_file:
        new_file.write(file.content)
    conv(src)
    time.sleep(2) # засыпаем на пару секунд, даем прогрмме время для конвертации
                  # чем тяжелее сообщение, тем больше времени потребуется
                  # можно дополнить динамической логикой
    send_file = open(src + '_to_wav.wav', 'rb')
    os.rename(src + '_to_wav.wav', 'audio_message_' + message.voice.file_id + '_to_wav.wav')
    rename_audio_file = open('audio_message_' + message.voice.file_id + '_to_wav.wav', 'rb')
    bot.send_document(message.chat.id, rename_audio_file)
    send_file.close()
    rename_audio_file.close()
    os.remove(os.getcwd() + message.voice.file_id)
    os.remove('audio_message_' + message.voice.file_id + '_to_wav.wav')


while True:
    try:
        bot.polling(none_stop=True)

    except Exception as e:
        print(e)
        time.sleep(15)
