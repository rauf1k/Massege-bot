import os
import sys
import asyncio
import threading
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QLineEdit, QPushButton, QScrollArea
from telethon.sync import TelegramClient
from telethon.tl.types import InputPeerSelf


class BotThread(QtCore.QThread):
    log_signal = QtCore.pyqtSignal(str)
    finished_signal = QtCore.pyqtSignal()

    def __init__(self, api_id, api_hash, phone_number, delay_between_messages, interval_between_batches, code_entry):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.delay_between_messages = delay_between_messages
        self.interval_between_batches = interval_between_batches
        self.stop_event = threading.Event()
        self.client = None
        self.code_entry = code_entry  # Поле для ввода кода подтверждения

    def run(self):
        asyncio.run(self.run_bot())

    async def run_bot(self):
        self.client = TelegramClient('session_name', self.api_id, self.api_hash)

        async def code_callback():
            self.log_signal.emit("Введите код подтверждения, отправленный на ваш номер.")
            while not self.code_entry.text():  # Ждем пока пользователь не введет код
                await asyncio.sleep(0.5)  # Ожидание перед повторной проверкой
            return self.code_entry.text()

        # Попытка входа с обработкой кода подтверждения
        await self.client.start(phone=self.phone_number, code_callback=code_callback)

        while not self.stop_event.is_set():  # Проверка на остановку
            message_to_send = await self.get_last_saved_message()
            if not message_to_send:
                self.log_signal.emit('Нет сообщений в "Избранном". Рассылка не выполнена.')
                return

            await self.send_messages(message_to_send)

            self.log_signal.emit(f'Ждем {self.interval_between_batches} секунд перед следующей рассылкой.')
            await asyncio.sleep(self.interval_between_batches)  # Задержка перед новой рассылкой

        self.log_signal.emit("Бот остановлен.")
        await self.client.disconnect()  # Отключаемся от клиента

    async def get_last_saved_message(self):
        """Получаем последнее сообщение из 'Избранного'."""
        async for message in self.client.iter_messages(InputPeerSelf(), limit=1):
            return message.text  # Возвращаем текст последнего сообщения

    async def send_messages(self, message_to_send):
        """Отправляем сообщение всем группам, каналам и чатам."""
        dialogs = await self.client.get_dialogs(limit=100)

        for dialog in dialogs:
            try:
                recipient = dialog.entity

                if (hasattr(recipient, 'broadcast') and recipient.broadcast) or \
                        (hasattr(recipient, 'megagroup') and recipient.megagroup):
                    await self.client.send_message(recipient, message_to_send)
                    self.log_signal.emit(f'Сообщение отправлено в группу/канал: {recipient.title}')
                elif hasattr(recipient, 'participant_count'):
                    await self.client.send_message(recipient, message_to_send)
                    self.log_signal.emit(f'Сообщение отправлено в группу: {recipient.title}')
                else:
                    self.log_signal.emit(f'Пропущено: {recipient.title} (не группа и не канал)')

                if self.stop_event.is_set():
                    self.log_signal.emit("Бот остановлен.")
                    break

                await asyncio.sleep(self.delay_between_messages)
            except Exception as e:
                self.log_signal.emit(f'Ошибка отправки сообщения: {e}')

    def stop(self):
        self.stop_event.set()


class BotApp(QWidget):
    def __init__(self):
        super().__init__()

        if getattr(sys, 'frozen', False):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(__file__)

        background_image_path = os.path.join(application_path, "background.jpg")

        self.setWindowTitle("m3f3dr0nka")
        self.setGeometry(100, 100, 600, 600)

        self.setAutoFillBackground(True)
        palette = self.palette()
        background_image = QtGui.QPixmap(background_image_path)
        palette.setBrush(self.backgroundRole(), QtGui.QBrush(background_image))
        self.setPalette(palette)

        layout = QVBoxLayout()

        self.api_id_entry = self.create_input_field("API ID:")
        self.api_hash_entry = self.create_input_field("API Hash:")
        self.phone_entry = self.create_input_field("Номер телефона:")
        self.delay_entry = self.create_input_field("Задержка между сообщениями (в секундах):")
        self.interval_entry = self.create_input_field("Задержка между рассылками (в секундах):")
        self.code_entry = self.create_input_field("Код подтверждения:")

        self.start_button = QPushButton("Старт")
        self.start_button.setFixedHeight(50)
        self.start_button.setStyleSheet(
            "background-color: black; color: white; font-weight: bold; border-radius: 10px; padding: 15px;")
        self.start_button.clicked.connect(self.start_bot)

        self.stop_button = QPushButton("Стоп")
        self.stop_button.setFixedHeight(50)
        self.stop_button.setStyleSheet(
            "background-color: black; color: white; font-weight: bold; border-radius: 10px; padding: 15px;")
        self.stop_button.clicked.connect(self.stop_bot)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)

        self.log_output = QScrollArea()
        self.log_output.setWidgetResizable(True)
        self.log_widget = QLabel()
        self.log_output.setWidget(self.log_widget)
        self.log_widget.setStyleSheet("background-color: rgba(46, 26, 71, 200); color: lightgreen;")
        self.log_widget.setWordWrap(True)

        layout.addWidget(self.api_id_entry)
        layout.addWidget(self.api_hash_entry)
        layout.addWidget(self.phone_entry)
        layout.addWidget(self.delay_entry)
        layout.addWidget(self.interval_entry)
        layout.addWidget(self.code_entry)
        layout.addLayout(button_layout)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

        self.bot_thread = None

    def create_input_field(self, placeholder):
        input_field = QLineEdit(self)
        input_field.setPlaceholderText(placeholder)
        input_field.setStyleSheet("background-color: rgba(255, 255, 255, 150); border-radius: 10px; padding: 10px;")
        return input_field

    def log(self, message):
        current_text = self.log_widget.text()
        self.log_widget.setText(current_text + message + "\n")

    def start_bot(self):
        self.log("Запуск бота...")
        api_id = self.api_id_entry.text()
        api_hash = self.api_hash_entry.text()
        phone_number = self.phone_entry.text()

        try:
            delay_between_messages = int(self.delay_entry.text())
            interval_between_batches = int(self.interval_entry.text())
        except ValueError:
            self.log("Ошибка: Убедитесь, что задержки введены в виде чисел.")
            return

        self.bot_thread = BotThread(api_id, api_hash, phone_number, delay_between_messages, interval_between_batches, self.code_entry)
        self.bot_thread.log_signal.connect(self.log)
        self.bot_thread.finished_signal.connect(self.on_bot_finished)
        self.bot_thread.start()

    def stop_bot(self):
        self.log("Остановка бота...")
        if self.bot_thread:
            self.bot_thread.stop()

    def on_bot_finished(self):
        self.log("Бот завершил свою работу.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    bot_app = BotApp()
    bot_app.show()
    sys.exit(app.exec_())
