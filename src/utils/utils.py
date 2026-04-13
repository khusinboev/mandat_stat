from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def extract_unique_code(text: str):
    return words[1] if len((words := text.split())) > 1 else None


def build_inline_keyboard(markup_text: str) -> InlineKeyboardMarkup:
    keyboard = []
    for column in markup_text.strip().split("\n"):
        keyboard.append([
            InlineKeyboardButton(text=btn_text.strip(), url=btn_url.strip())
            for btn_text, btn_url in [part.split("|") for part in column.split("&")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
