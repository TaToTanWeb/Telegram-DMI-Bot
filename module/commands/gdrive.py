"""/drive command"""
from pydrive2.files import GoogleDriveFile
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot
from telegram.ext import CallbackContext
from module.shared import check_log
from module.debug import log_error
from module.data.vars import TEXT_IDS, PLACE_HOLDER
from module.utils.multi_lang_utils import get_locale
from module.utils.drive_utils import drive_utils


def drive(update: Update, context: CallbackContext) -> None:
    """Called by the /drive command.
    Lets the user navigate the drive folders, if he has the permissions

    Args:
        update: update event
        context: context passed by the handler
    """
    check_log(update, "drive")
    chat_id: int = update.message.chat_id
    locale: str = update.message.from_user.language_code
    if chat_id < 0:
        context.bot.sendMessage(
            chat_id=chat_id, text=get_locale(locale, TEXT_IDS.GROUP_WARNING_TEXT_ID).replace(PLACE_HOLDER, "/drive")
        )
        return

    file_list = drive_utils.list_files()
    if file_list:
        # keyboard that allows the user to navigate the folder
        keyboard = get_files_keyboard(file_list, row_len=3)
        context.bot.sendMessage(
            chat_id=chat_id,
            text=get_locale(locale, TEXT_IDS.DRIVE_HEADER_TEXT_ID),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        context.bot.sendMessage(
            chat_id=chat_id,
            text=get_locale(locale, TEXT_IDS.DRIVE_ERROR_DEVS_TEXT_ID),
        )


def drive_handler(update: Update, context: CallbackContext) -> None:
    """Called by any of the buttons of the /drive command.
    Allows the user to navigate in the google drive and download files

    Args:
        update: update event
        context: context passed by the handler
    """
    bot: Bot = context.bot

    query_data: str = update.callback_query.data.replace("drive_file_", "")
    chat_id: int = update.callback_query.from_user.id
    message_id: int = update.callback_query.message.message_id
    locale: str = update.callback_query.from_user.language_code
    fetched_file: GoogleDriveFile = drive_utils.get_file(query_data)

    # the user clicked on a folder
    if fetched_file['mimeType'] == "application/vnd.google-apps.folder":
        file_list = drive_utils.list_files(fetched_file['id'])

        if file_list is None:
            bot.editMessageText(
                chat_id=chat_id,
                message_id=message_id,
                text=get_locale(locale, TEXT_IDS.DRIVE_ERROR_DEVS_TEXT_ID),
            )
            return

        # keyboard that allows the user to navigate the folder
        keyboard = get_files_keyboard(file_list)

        if (
            len(fetched_file['parents']) > 0
            and fetched_file['parents'][0]['id'] != '0ADXK_Yx5406vUk9PVA'
        ):
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=get_locale(locale, TEXT_IDS.BACK_BUTTON_TEXT_TEXT_ID),
                        callback_data=f"drive_file_{fetched_file['parents'][0]['id']}",
                    )
                ]
            )

        bot.editMessageText(
            chat_id=chat_id,
            message_id=message_id,
            text=fetched_file['title'] + ":",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # the user clicked on a google docs
    elif fetched_file['mimeType'] == "application/vnd.google-apps.document":
        bot.sendMessage(
            chat_id=chat_id,
            text=get_locale(locale, TEXT_IDS.DRIVE_ERROR_GFILE_TEXT_ID).replace(PLACE_HOLDER, fetched_file['exportLinks']['application/pdf'])
        )

    else:  # the user clicked on a file
        try:
            file_d = drive_utils.get_file(fetched_file['id'])
            if int(file_d['fileSize']) < 5e7:
                f = file_d.GetContentIOBuffer()
                f.name = fetched_file['title']
                bot.sendChatAction(chat_id=chat_id, action="UPLOAD_DOCUMENT")
                bot.sendDocument(chat_id=chat_id, document=f)

            else:
                bot.sendMessage(
                    chat_id=chat_id,
                    text=get_locale(locale, TEXT_IDS.DRIVE_ERROR_TOO_BIG_TEXT_ID).replace(PLACE_HOLDER, file_d['alternateLink'])
                )

        # pylint: disable=broad-except
        except Exception as err:
            log_error(header="drive_handler", error=err)

    update.callback_query.answer()  # stops the spinning


def get_files_keyboard(file_list: list, row_len: int = 2) -> list:
    """Called by :meth:`drive` and :meth:`drive_handler`.
    Generates the InlineKeyboard that allows the user to navigate among the files in the list

    Args:
        file_list: list of files
        row_len: lenght of the row. Defaults to 2

    Returns:
        InlineKeyboard
    """
    formats = {
        **{"pdf": "📕 "},
        **dict.fromkeys([' a', 'b', 'c'], 10),
        **dict.fromkeys(["doc", "docx", "txt"], "📄 "),
        **dict.fromkeys(["jpg", "png", "gif"], "📷 "),
        **dict.fromkeys(["rar", "zip"], "📦 "),
        **dict.fromkeys(["out", "exe"], "⚙ "),
        **dict.fromkeys(["c", "cpp", "h", "py", "java", "js", "html", "php"], "💻 "),
    }

    keyboard = []

    for i, file in enumerate(file_list):

        if file['mimeType'] == "application/vnd.google-apps.folder":
            icon = "🗂 "

        else:
            # get last 5 characters of strings
            file_format = file['title'][-5:]
            file_format = file_format.split(".")  # split file_format per "."
            file_format = file_format[-1]  # get last element of file_format
            icon = formats.get(file_format, "📄 ")

        keyboard_button = InlineKeyboardButton(
            text=f"{icon} {file['title']}", callback_data="drive_file_" + file['id']
        )

        # pylint: disable=pointless-string-statement
        """"
        We add a new row when we have added the number of buttons specified by {row_len} argument
        In this way we have a maximum of {row_len} buttons in a row.
        """

        if i % row_len == 0:
            keyboard.append([keyboard_button])

        else:
            keyboard[i // row_len].append(keyboard_button)

    return keyboard
