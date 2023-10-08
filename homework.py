import os
import sys
import requests
import logging
import telegram
import time
from http import HTTPStatus
import json

from logging import StreamHandler
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - [%(levelname)s] - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщений ботом в телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Бот отправил сообщение в чат')
    except telegram.error.TelegramError as error:
        logger.error(f'Сбой при отправке сообщения в чат - {error}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload,
        )
    except requests.exceptions.RequestException as error:
        raise Exception(f'Ошибка при запросе к API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        raise requests.exceptions.StatusCodeException(
            'Неверный код ответа API'
        )
    try:
        return homework_statuses.json()
    except json.decoder.JSONDecodeError:
        raise Exception('Ответ не преобразован в json')


def check_response(response):
    """Проверяет корректность ответа API и возвращает список домашних работ."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь')
    check_list_homeworks = response.get('homeworks')
    if check_list_homeworks is None:
        raise KeyError('Ключ "homeworks" не доступен')
    if not isinstance(check_list_homeworks, list):
        raise TypeError('Ответ API  оключу "homeworks" не список')
    if len(check_list_homeworks) > 0:
        return check_list_homeworks
    else:
        logger.debug('В текущей проверке новые статусы Д-З отсутсвуют')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    try:
        homework_name = str(homework['homework_name'])
    except KeyError:
        raise KeyError('Ошибка ключа "homework_name"')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise KeyError('Статус не найден')
    if homework['status'] in HOMEWORK_VERDICTS:
        verdict = str(HOMEWORK_VERDICTS[homework['status']])
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    if (PRACTICUM_TOKEN is None
            or TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None):
        return False
    return True


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        error_txt = (
            'Обязательные переменные окружения отсутствуют. '
            'Принудительная остановка Бота.'
        )
        logger.critical(error_txt)
        return None
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if isinstance(response, dict):
                check_response_hw = check_response(response)
                if isinstance(check_response_hw, list):
                    for hw in check_response_hw:
                        if isinstance(response, dict):
                            message = parse_status(hw)
                            send_message(bot, message)
                        else:
                            logger.error('Домашняя работа не словарь')
            else:
                logger.error('Ответ API.Yandex не корректен')
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
