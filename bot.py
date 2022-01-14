import requests
from requests.sessions import session
from selenium import webdriver
from bs4 import BeautifulSoup, element
from aiogram import Bot, types
from aiogram.types import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.message import ContentType
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.utils.emoji import emojize
from aiogram.utils.markdown import text, bold, italic, code, pre

from config import TOKEN, API_KEY


session = requests.session()
session.headers = {
    'X-API-KEY': f'{API_KEY}',
    'Content-Type': 'application/json',
}


bot = Bot(token=TOKEN)
dp = Dispatcher(bot)


async def get_films_cinema(query) -> list:
    response = session.get('https://kinopoiskapiunofficial.tech/api/v2.2/films',
                           params={'keyword': query})
    json = response.json()
    films_cinema = json.get("items", [])

    return films_cinema


async def get_films_rezka(query) -> list:
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")

    driver = webdriver.Chrome(chrome_options=options)
    my_url = f'https://kinopub.me/search/?do=search&subaction=search&q={query}'

    driver.get(my_url)
    driver.refresh()

    response = driver.page_source
    soup = BeautifulSoup(response, 'html.parser')

    films_rezka = soup.findAll('div', class_='b-content__inline_item')

    return films_rezka


# Хэндлер на команду /start
@dp.message_handler(commands=['start'], chat_type=[types.ChatType.GROUP, types.ChatType.CHANNEL, types.ChatType.PRIVATE])
async def command_start(message: types.Message):
    name_bot = await bot.get_me()

    message_text = text(bold('Привет!'), f'Я КиноБот {name_bot.first_name}.',
                        '\n\nЕсли ты хочешь посмотреть', italic('фильм/сериал/мультфильм'), 'в хорошем качестве', 'то я постараюсь помочь тебе найти его. Используй клавиатуру ниже, чтобы вызывать команды или просто напиши мне ключевые слова. \n\nПодхожу для групп, каналов и личных сообщений.')

    await bot.send_message(message.chat.id, message_text, parse_mode=ParseMode.MARKDOWN)


# Хэндлер отработки нажатий кнопок
@dp.callback_query_handler(lambda callback_query: True)
async def some_callback_handler(callback_query: types.CallbackQuery):
    # Запрос описание определенного фильма (Кинопоиск)
    chatId = callback_query.message.chat.id

    kinoId = callback_query.data
    dataFilm = await request_cinema(kinoId)

    poster_url = dataFilm['posterUrl']
    name_film = dataFilm['nameRu']
    year = dataFilm['year']
    country = dataFilm['countries'][0].get('country')
    ratingKinopoisk = dataFilm['ratingKinopoisk']
    ratingImdb = dataFilm['ratingImdb']
    type = dataFilm['type'].lower()
    desc = dataFilm['description']

    film = dataFilm['webUrl'].replace(".ru", ".gg")

    # Инлайн кнопка для просмотра фильма (Кинопоиск)
    btn_show_name = InlineKeyboardButton(
        'Посмотреть на Кинопоиске', url=film)
    btn_show = InlineKeyboardMarkup().add(btn_show_name)

    await bot.send_photo(chatId, poster_url, caption=f'{name_film}\n\nДата выхода: {year} г.\nСтрана: {country}.\nРейтинги: Кинопоиск {ratingKinopoisk}, Imdb {ratingImdb}.\nОписание: {desc}\n\nТип: {type}.', reply_markup=btn_show)


# Хэндлер запрос на Кинопоиск
async def request_cinema(kinopoiskId):
    # Запрос описания (Кинопоиск)
    response = session.get(
        f'https://kinopoiskapiunofficial.tech/api/v2.2/films/{kinopoiskId}')
    json = response.json()

    return json


# Хэндлер на текст
@dp.message_handler(content_types=ContentType.TEXT, chat_type=[types.ChatType.GROUP, types.ChatType.CHANNEL, types.ChatType.PRIVATE])
async def message_response_text(message: types.Message):
    query = message.text

    await bot.send_message(message.chat.id, f'Собираю информацию по "{query}", подожди немного.')

    # Запрос фильмов (Кинопоиск)
    films_cinema = await get_films_cinema(query)

    # Запрос фильмов (HDrezka)
    films_rezka = await get_films_rezka(query)

    # Проверка, полученных ответов/фильмов с (Кинопоиск) и (HDrezka)
    if len(films_cinema) == 0 and len(films_rezka) == 0:
        await bot.send_message(message.chat.id, f'По "{query}" ничего не найдено, проверьте правильность запроса.')
        return

    # Инлайн 5 кнопок (Кинопоиск)
    url_kb_cinema = InlineKeyboardMarkup(row_width=1)

    for f in films_cinema[:5]:
        name_cinema = f['nameRu']
        year_cinema = f['year']
        type_cinema = f['type'].lower()
        kinopoiskId = f['kinopoiskId']
        await request_cinema(kinopoiskId)
        if name_cinema is None or year_cinema is None:
            continue
        url_kb_buttons = InlineKeyboardButton(
            text=f'{name_cinema} ({year_cinema}) ({type_cinema})', callback_data=str(kinopoiskId))
        url_kb_cinema.add(url_kb_buttons)

    await bot.send_message(message.chat.id, text=f'Кинопоиск - по запросу "{query}" найдено:', reply_markup=url_kb_cinema)

    # Инлайн 5 кнопок (HDrezka)
    url_kb_rezka = InlineKeyboardMarkup(row_width=1)

    for f in films_rezka[:5]:
        name_rezka = f.find(
            'div', class_='b-content__inline_item-link').find('a').text
        year_rezka = f.find(
            'div', class_='b-content__inline_item-link').find('div').text.split(',')[0]
        type_rezka = f.find('span', class_='cat').find(
            'i', class_='entity').text
        url_rezka = f.find(
            'div', class_='b-content__inline_item-link').a['href']
        if name_rezka is None or year_rezka is None:
            continue
        url_kb_buttons = InlineKeyboardButton(
            text=f'{name_rezka} ({year_rezka}) ({type_rezka})', url=url_rezka)
        url_kb_rezka.add(url_kb_buttons)

    await bot.send_message(message.chat.id, text=f'HDrezka - по запросу "{query}" найдено:', reply_markup=url_kb_rezka)


# Хэндлер на любую команду
@dp.message_handler(content_types=ContentType.ANY, chat_type=[types.ChatType.GROUP, types.ChatType.CHANNEL, types.ChatType.PRIVATE])
async def message_unknown(message: types.Message):
    message_text = text(emojize('Я не знаю, что с этим делать :pensive:'),
                        bold('\nЯ просто напомню,'), 'что есть команда', '/start')

    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
