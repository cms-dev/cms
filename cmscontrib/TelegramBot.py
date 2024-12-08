#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2024 Luca Versari <veluca93@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import collections
from sqlalchemy.orm import Query

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyParameters

try:
    collections.MutableMapping
except:
    # Monkey-patch: Tornado 4.5.3 does not work on Python 3.11 by default
    collections.MutableMapping = collections.abc.MutableMapping

import datetime
import argparse
import asyncio
import html
import logging
import os

# We use yaml instead of json or similar because
import yaml

from cms import config
from cms.conf import ConfigError
from cms.db import ask_for_contest, Announcement, Question, Participation
from cms.db.session import SessionGen
from cms.util import contest_id_from_args

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)


logger = logging.getLogger(__name__)

HELP_MESSAGE = """
Bot to interact with the questions of a CMS contest. \
This bot will automatically post new questions in \
this channel, and allows you to reply.

In particular, you can use the <i>inline keyboard</i> to reply to \
questions with built-in answers or to ignore questions, and the \
following command:

<pre>/answer Reply here</pre>
Send this command while replying to question to reply with the text \
"Reply here".

Currently, announcements are not supported in multi-contest mode.
"""

HELP_MESSAGE_ANNOUNCEMENT = """
Bot to interact with questions and announcements of a CMS contest. \
This bot will automatically post new questions and announcements in \
this channel, and allows you to create announcements and reply to \
questions.

In particular, you can use the <i>inline keyboard</i> to reply to \
questions with built-in answers or to ignore questions, and you \
can use the following commands:

<pre>/answer Reply here</pre>
Send this command while replying to question to reply with the text \
"Reply here".

<pre>/announcement Announcement subject
Announcement body
</pre>
Send an announcement with title "Announcement subject" and body \
"Announcement body". More precisely, the subject of the announcement \
ends at the end of the first line.
"""


def sqlalchemy_to_dict(obj):
    d = obj.get_attrs()
    d["id"] = obj.id
    return d


class TelegramBot:
    def __init__(self, chat_id, token, contest_id) -> None:
        self.chat_id = int(chat_id)
        self.contest_id = contest_id
        self.application = (
            ApplicationBuilder()
            .token(token)
            .read_timeout(60)
            .get_updates_read_timeout(60)
            .write_timeout(60)
            .get_updates_write_timeout(60)
            .build()
        )
        self.application.add_handler(
            CommandHandler("start", self.send_help_message))
        self.application.add_handler(
            CommandHandler("help", self.send_help_message))
        if self.contest_id is not None:
            self.application.add_handler(
                CommandHandler("announcement", self.send_announcement)
            )
        self.application.add_handler(
            CommandHandler("answer", self.custom_answer))
        self.application.add_handler(CallbackQueryHandler(self.answer))

        self.question_storage_dir = os.path.join(
            config.data_dir, "telegram", "question"
        )
        self.announcement_storage_dir = os.path.join(
            config.data_dir, "telegram", "announcement"
        )
        os.makedirs(self.question_storage_dir, exist_ok=True)
        os.makedirs(self.announcement_storage_dir, exist_ok=True)

        self.msg_id_to_qid = dict()

        def load_status(directory):
            ans = dict()
            with os.scandir(directory) as it:
                for entry in it:
                    if not entry.is_file():
                        logging.warn(
                            f"{directory} contains a non-file {entry.name}")
                        continue
                    with open(os.path.join(directory, entry.name)) as f:
                        try:
                            data = yaml.safe_load(f.read())
                            assert self.file_name(data["id"]) == entry.name
                            ans[data["id"]] = data
                        except:
                            logger.warn(
                                f"Invalid stored file {entry.name} in {directory}"
                            )
            return ans

        self.question_status = load_status(self.question_storage_dir)
        self.announcement_status = load_status(self.announcement_storage_dir)

        for (qid, q) in self.question_status.items():
            self.msg_id_to_qid[q["msg_id"]] = qid

    def file_name(self, id):
        return f"{id}.yaml"

    async def send_help_message(self, update, context):
        del update
        if self.contest_id is None:
            await context.bot.send_message(
                chat_id=self.chat_id, text=HELP_MESSAGE, parse_mode="HTML"
            )
        else:
            await context.bot.send_message(
                chat_id=self.chat_id,
                text=HELP_MESSAGE_ANNOUNCEMENT,
                parse_mode="HTML",
            )

    async def custom_answer(self, update, context):
        if update.effective_chat.id != self.chat_id:
            logging.warning(
                f"answer from unknown chat {update.effective_chat.id}")
            return
        text = update.message.text
        reply_to = update.message.reply_to_message
        if reply_to is not None:
            reply_to = reply_to.message_id
        try:
            text = text.split(" ", 1)[1]
        except:
            await context.bot.send_message(
                chat_id=self.chat_id,
                text="Missing reply text",
                parse_mode="HTML",
                reply_parameters=ReplyParameters(update.message.message_id),
            )
            return
        qid = self.msg_id_to_qid.get(reply_to, None)
        if qid is None:
            await context.bot.send_message(
                chat_id=self.chat_id,
                text="You can only use /answer in replies to questions!",
                parse_mode="HTML",
                reply_parameters=ReplyParameters(update.message.message_id),
            )
            return

        text = text.strip()
        with SessionGen() as ses:
            question = Question.get_from_id(qid, ses)
            question.reply_timestamp = datetime.datetime.now()
            question.ignored = False
            question.reply_text = text
            question.reply_subject = ""
            ses.add(question)
            ses.commit()

    async def answer(self, update, context):
        if update.effective_chat.id != self.chat_id:
            logging.warning(
                f"reply from unknown chat {update.effective_chat.id}")
            return
        text = update.callback_query.data
        qid, text = text.split(" ", 1)
        qid = int(qid)
        text = text.strip()
        with SessionGen() as ses:
            question = Question.get_from_id(qid, ses)
            if text == "IGNORE":
                question.ignored = True
                question.reply_timestamp = None
            elif text == "REMOVE":
                question.ignored = False
                question.reply_timestamp = None
                question.reply_text = None
                question.reply_subject = None
            else:
                question.reply_timestamp = datetime.datetime.now()
                question.ignored = False
                question.reply_text = ""
                question.reply_subject = text
            ses.add(question)
            ses.commit()
        await update.callback_query.answer()

    async def send_announcement(self, update, context):
        if update.effective_chat.id != self.chat_id:
            logging.warning(
                f"announcement from unknown chat {update.effective_chat.id}"
            )
            return
        text = update.message.text
        try:
            subject, text = text.split("\n", 1)
        except:
            await context.bot.send_message(
                chat_id=self.chat_id,
                text="Missing announcement body",
                parse_mode="HTML",
                reply_parameters=ReplyParameters(update.message.message_id),
            )
            return
        subject = subject.split(" ", 1)[1]
        text = text.strip()
        announcement = Announcement(
            subject=subject, text=text, timestamp=datetime.datetime.now()
        )
        announcement.contest_id = self.contest_id
        with SessionGen() as ses:
            ses.add(announcement)
            ses.commit()

    async def run(self):
        async with self.application:
            try:
                await self.application.start()
                commands = [("help", "get help"),
                            ("answer", "reply to a question")]
                if self.contest_id is not None:
                    commands.append(("announcement", "send an announcement"))
                await self.application.bot.set_my_commands(())
                await self.application.updater.start_polling()
                await self.db_loop()
            finally:
                await self.application.updater.stop()
                await self.application.stop()

    async def _store(self, obj, store, directory, callback):
        existing = store.get(obj["id"], dict())
        has_changed = False
        for (k, v) in obj.items():
            if existing.get(k, None) != v:
                has_changed = True

        if has_changed:
            obj_id = obj["id"]
            obj = await callback(existing, obj)
            store[obj_id] = obj
            with open(os.path.join(directory, self.file_name(obj_id)), "w") as f:
                f.write(yaml.safe_dump(obj))

    async def store_question(self, question, changed_callback):
        await self._store(
            question, self.question_status, self.question_storage_dir, changed_callback
        )

    async def store_announcement(self, announcement, changed_callback):
        await self._store(
            announcement,
            self.announcement_status,
            self.announcement_storage_dir,
            changed_callback,
        )

    async def question_callback(self, old, new):
        subject = html.escape(new["subject"])
        text = html.escape(new["text"])
        qid = new["id"]
        msg = f"<b>New question from {new['username']}</b>\nSubject: <i>{subject}</i>\n\n{text}"

        if new["ignored"]:
            msg += f"\n\n<i>Ignored</i>"
        elif new["reply_text"] is not None:
            ans_subject = html.escape(new["reply_subject"])
            ans_text = html.escape(new["reply_text"])
            msg += f"\n\n<b>Answer: </b><i>{ans_subject}</i>\n\n<i>{ans_text}</i>"
        else:
            msg = f"#todo\n{msg}\n\nReply with <code>/answer your_reply_here</code> for a custom reply"

        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes", callback_data=f"{qid} Yes"),
                    InlineKeyboardButton("No", callback_data=f"{qid} No"),
                ],
                [
                    InlineKeyboardButton(
                        "No comment", callback_data=f"{qid} No comment"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Answered in task description",
                        callback_data=f"{qid} Answered in task description",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Invalid question", callback_data=f"{qid} Invalid question"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Ignore", callback_data=f"{qid} IGNORE"),
                ],
                [
                    InlineKeyboardButton(
                        "Remove answer", callback_data=f"{qid} REMOVE"),
                ],
            ]
        )

        if "msg_id" not in old:
            msg_id = (
                await self.application.bot.send_message(
                    self.chat_id, text=msg, parse_mode="HTML", reply_markup=reply_markup
                )
            ).message_id
        else:
            msg_id = old["msg_id"]
            await self.application.bot.edit_message_text(
                msg,
                message_id=msg_id,
                chat_id=self.chat_id,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        new["msg_id"] = msg_id
        self.msg_id_to_qid[msg_id] = qid
        return new

    async def announcement_callback(self, old, new):
        subject = html.escape(new["subject"])
        text = html.escape(new["text"])
        text = f"<b>New announcement</b>\nSubject: <i>{subject}</i>\n\n{text}"
        if "msg_id" not in old:
            msg_id = (
                await self.application.bot.send_message(
                    self.chat_id, text=text, parse_mode="HTML"
                )
            ).message_id
        else:
            msg_id = old["msg_id"]
            await self.application.bot.edit_message_text(
                text, message_id=msg_id, chat_id=self.chat_id, parse_mode="HTML"
            )
        new["msg_id"] = msg_id
        return new

    async def db_loop(self):
        while True:
            logger.debug("Reading questions and announcements from DB")
            with SessionGen() as session:
                query = session.query(Question).join(Participation)
                if self.contest_id is not None:
                    query = query.filter(
                        Participation.contest_id == self.contest_id)

                def q_to_dict(q):
                    d = sqlalchemy_to_dict(q)
                    d["username"] = q.participation.user.username
                    return d

                qs = [q_to_dict(x) for x in query.all()]
                if self.contest_id is None:
                    anns = []
                else:
                    anns = [
                        sqlalchemy_to_dict(x)
                        for x in session.query(Announcement)
                        .filter(Announcement.contest_id == self.contest_id)
                        .all()
                    ]
            for q in qs:
                await self.store_question(q, self.question_callback)
            for ann in anns:
                await self.store_announcement(ann, self.announcement_callback)

            await asyncio.sleep(1)


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(description="Telegram bot.")

    # unsed, but passed by ResourceService
    parser.add_argument("shard", default="", help="unused", nargs="?")
    contest_id_help = (
        "id of the contest to post questions and announcements for, "
        "or ALL to serve all contests and ignore announcements"
    )
    parser.add_argument("-c", "--contest-id", type=str, help=contest_id_help)

    args = parser.parse_args()

    contest_id = contest_id_from_args(args.contest_id, ask_for_contest)

    if contest_id == "ALL":
        contest_id = None

    if config.telegram_bot_token is None or config.telegram_bot_chat_id is None:
        raise ConfigError(
            "Need to configure the Telegram bot before starting it")

    bot = TelegramBot(
        config.telegram_bot_chat_id, config.telegram_bot_token, contest_id
    )

    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
