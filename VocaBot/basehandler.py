class BaseHandler:
    def __init__(self, bot, update):
        self.bot = bot
        self.update = update

        self.inline = False

        if update.message:
            self.user = update.message.from_user
            self.chat = update.message.chat
        elif update.edited_message:
            user = update.edited_message.from_user
            chat = update.edited_message.chat
        elif update.inline_query:
            user = update.inline_query.from_user
        elif update.chosen_inline_result:
            user = update.chosen_inline_result.from_user
        elif update.callback_query:
            user = update.callback_query.from_user
            chat = update.callback_query.message.chat if update.callback_query.message else None