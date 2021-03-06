import re
from abc import ABC, abstractmethod
from functools import lru_cache
import pathlib
import requests

import gspread
from gspread.utils import a1_to_rowcol


# set the credentials.json file path, by default, the file is searched in the pvme_docs_generator/ folder
module_path = pathlib.Path(__file__).parent.absolute()
CREDENTIALS_FILE = "{}/credentials.json".format(module_path)

# set the PVME price spreadsheet link (full link)
PVME_SPREADSHEET = "https://docs.google.com/spreadsheets/d/1nFepmgXBFh1Juc0Qh5nd1HLk50iiFTt3DHapILozuIM/edit#gid=0"

# base domain used as parent setting for twitch embeds
BASE_DOMAIN = "towsti.github.io"


class Sphinx(ABC):
    @staticmethod
    @abstractmethod
    def format_sphinx_rst(message, doc_info):
        raise NotImplementedError()


class MKDocs(ABC):
    @staticmethod
    @abstractmethod
    def format_mkdocs_md(message):
        raise NotImplementedError()


class PVMEBotCommand(MKDocs):
    """Format lines starting with . (bot commands)."""
    @staticmethod
    def format_mkdocs_md(message):
        if not message.bot_command:
            return

        if message.bot_command == '.':
            message.bot_command = ''
        elif message.bot_command == "..":
            message.bot_command = '.'
        elif message.bot_command.startswith((".tag:", ".pin:", ".tag:")):
            message.bot_command = ''
        elif message.bot_command.startswith((".img:", ".file:")):
            # todo: temporary parsing to get a general idea
            link = message.bot_command.split(':', 1)
            message.bot_command = EmbedLink.generate_embed(link[1])


class Section(MKDocs):
    """Format lines starting with > __**section**__ to """
    PATTERN = re.compile(r"(?:^|\n)>\s(.+?)(?=\n|$)")

    @staticmethod
    def format_mkdocs_md(message):
        matches = [match for match in re.finditer(Section.PATTERN, message.content)]

        for match in reversed(matches):
            section_name = re.sub(r"[*_]*", '', match.group(1))
            section_name_formatted = "## {}".format(section_name)

            # remove ':' at the end of a section name to keep ry happy
            if section_name_formatted.endswith(':'):
                section_name_formatted = section_name_formatted[:-1]

            message.content = message.content[:match.start()] + section_name_formatted + message.content[match.end():]


class Emoji(MKDocs):
    """<concBlast:1234> -> <img src="https://cdn.discordapp.com/emojis/535533809924571136.png?v=1" class="emoji">"""
    PATTERNS = [(re.compile(r"<:([^:]{2,}):([0-9]+)>"), ".png"),
                (re.compile(r"<:a:([^:]+):([0-9]+)>"), ".gif")]

    @staticmethod
    def format_mkdocs_md(message):
        for pattern, extension in Emoji.PATTERNS:
            matches = [match for match in re.finditer(pattern, message.content)]
            for match in reversed(matches):
                emoji_formatted = "<img title=\"{}\" class=\"emoji\" alt=\"{}\" src=\"https://cdn.discordapp.com/emojis/{}{}?v=1\">".format(match.group(1), match.group(1), match.group(2), extension)
                message.content = message.content[:match.start()] + emoji_formatted + message.content[match.end():]


class DiscordMarkdownHTML(MKDocs):
    MKDOCS_PATTERNS = [(re.compile(r"__"), "<u>", "</u>")]

    @staticmethod
    def format_mkdocs_md(message):
        for pattern, start_symbol, end_symbol in DiscordMarkdownHTML.MKDOCS_PATTERNS:
            matches = [match for match in re.finditer(pattern, message.content)]

            # remove any unclosed elements (to avoid "<u>text" without a closing "</u>")
            if len(matches) % 2 == 1:
                matches = matches[:-1]

            for index, match in enumerate(reversed(matches)):
                # set <u> or </u> based on if the match is even or uneven
                symbol = start_symbol if index % 2 else end_symbol

                message.content = message.content[:match.start()] + symbol + message.content[match.end():]


class EmbedLink(MKDocs):
    PATTERN = re.compile(
        # r'(?:[^<])'             # check for valid embed links (don't start with '<')
        r'(?:[^<])'
        r'((?:http|ftp)s?://'   # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'           # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'      # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'              # ...or ipv6
        r'(?::\d+)?'            # optional port
        r'(?:/?|[/?]\S+)'
        r'(?:[^ )\n\t\r]*))', re.IGNORECASE)         # anything at the end of the link

    @staticmethod
    def generate_embed(url: str) -> str:
        """Obtain the html embed url from a raw (unparsed) url.
        All common urls are checked for a fixed format in order to greatly reduce build time.
        For other url formats, the metadata is requested after which an embed is generated based on the metadata.

        :param url: raw unparsed url
        :return: html formatted embed url (None if no embed url is discovered)
        """
        # todo: open graph protocol formatting
        # todo: open graph protocol parsing for unknown urls
        # i.imgur (png) note: can be managed in else but about 90% of the urls are in this format so it speeds up
        if re.match(r"https?://i\.imgur\.com/([a-zA-Z0-9]+)\.png", url):
            embed = "<img class=\"media\" src=\"{}\">".format(url)

        # youtu.be
        elif match := re.match(r"https?://youtu\.be/([a-zA-Z0-9_\-]+)", url):
            embed = "<iframe class=\"media\" width=\"560\" height=\"315\" src=\"https://www.youtube.com/embed/{}\" frameborder=\"0\" allow=\"accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>".format(match.group(1))

        # youtube.com
        elif match := re.match(r"https?://(www\.)?youtube\.[a-z0-9.]*?/watch\?([0-9a-zA-Z$\-_.+!*'(),;/?:@=&#]*&)?v=([a-zA-Z0-9_\-]+)", url):
            embed = "<iframe class=\"media\" width=\"560\" height=\"315\" src=\"https://www.youtube.com/embed/{}\" frameborder=\"0\" allow=\"accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>".format(match.group(3))

        # clips.twitch.tv
        elif match := re.match(r"https?://clips\.twitch\.tv/([a-zA-Z]+)", url):
            # todo: embed not formatted correctly
            embed = "<iframe class=\"media\" src=\"https://clips.twitch.tv/embed?autoplay=false&clip={}&parent={}\" frameborder=\"0\" allowfullscreen=\"true\" scrolling=\"no\" height=\"315\" width=\"560\"></iframe>".format(match.group(1), BASE_DOMAIN)

        # twitch.tv/videos
        elif match := re.match(r"https?://www\.twitch\.tv/videos/([0-9a-zA-Z]+)", url):
            # todo: embed not formatted correctly
            embed = "<iframe class=\"media\" src=\"https://player.twitch.tv/?autoplay=false&video=v{}&parent={}\" frameborder=\"0\" allowfullscreen=\"true\" scrolling=\"no\" height=\"315\" width=\"560\"></iframe>".format(match.group(1), BASE_DOMAIN)

        # streamable
        elif match := re.match(r"https?://streamable\.com/([a-zA-Z0-9]+)", url):
            embed = "<iframe class=\"media\" src=\"https://streamable.com/o/{}\" frameborder=\"0\" scrolling=\"no\" width=\"560\" height=\"315\" allowfullscreen></iframe>".format(match.group(1))

        # pastebin
        elif match := re.match(r"https?://pastebin.com/([a-zA-Z0-9]+)", url):
            embed = "<iframe class=\"media\" src=\"https://pastebin.com/embed_iframe/{}?theme=dark\" style=\"width:560px;height:155px\"></iframe>".format(match.group(1))

        else:
            # gyazo
            if re.match(r"https?://gyazo\.com/([0-9a-fA-Z]+)", url):
                # todo: fetch api.gyazo.com to obtain the reformatted i.gyazo.com url
                adjusted_url = url

            # gfycat
            elif match := re.match(r"https?://gfycat\.com/([a-zA-Z0-9]+)", url):
                # todo: fetch api.gfycat.com to obtain the reformatted i.gyazo.com url
                adjusted_url = url

            # unknown url
            else:
                adjusted_url = url

            # obtain the type of embed from a request
            if adjusted_url.endswith(".gifv"):
                adjusted_url = re.sub(r"\.gifv$", ".mp4", adjusted_url)

            try:
                response = requests.head(adjusted_url)
                url_type = response.headers.get('content-type', '') if response.status_code == 200 else ''
            except requests.exceptions.RequestException:
                embed = None
            else:
                if url_type.startswith("image/"):
                    embed = "<img class=\"media\" src=\"{}\">".format(adjusted_url)
                elif url_type.startswith("video/"):
                    embed = "<video class=\"media\" autoplay loop muted controls><source src=\"{}\"></video>".format(adjusted_url)
                else:
                    embed = None

        return embed

    @staticmethod
    def format_mkdocs_md(message):
        # todo: character at the start of the embed is removed (e.g. '(' in github for contribution quick start)
        matches = [match for match in re.finditer(EmbedLink.PATTERN, message.content)]
        for match in reversed(matches):
            url_formatted = "<{}>".format(match.group(1))
            message.content = message.content[:match.start()] + url_formatted + message.content[match.end():]

        for match in matches:
            embed = EmbedLink.generate_embed(match.group(1))
            if embed:
                message.embeds.append(embed)


class LineBreak(MKDocs):
    PATTERN = re.compile(r"_ _")

    @staticmethod
    def format_mkdocs_md(message):
        message.content = re.sub(LineBreak.PATTERN, '', message.content)


class DiscordWhiteSpace(MKDocs):
    """Converts whitespace and tabs that would normally be converted to a single space in html/markdown
    to a special "empty" character. For now this is used over <pre> </pre> and &nbsp; due to inline code blocks

    todo: use &nbsp; instead of the weirdchamp "empty" character, this requires detecting code blocks
    """
    @staticmethod
    def format_mkdocs_md(message):
        message.content = re.sub(r"\t", '    ‎', message.content)

        matches = [match for match in re.finditer(r"( {2,})", message.content)]
        for match in reversed(matches):
            line_spaces = ' ‎' * len(match.group(1))
            message.content = message.content[:match.start()] + line_spaces + message.content[match.end():]

        message.content = re.sub(r"^ ", ' ‎', message.content)


class CodeBlock(MKDocs):
    # todo: current approach adds enter to start and end of block, consider improving this
    PATTERN = re.compile(r"```")

    @staticmethod
    def format_mkdocs_md(message):
        message.content = re.sub(CodeBlock.PATTERN, '\n```\n', message.content)


class PVMESpreadSheet(MKDocs):
    """Format "$data_pvme:Perks!H11$" to the price from the pvme-guides spreadsheet."""
    PATTERN = re.compile(r"\$data_pvme:([^!]+)!([^$]+)\$")

    @staticmethod
    @lru_cache(maxsize=None)
    def obtain_pvme_spreadsheet_data(worksheet):
        try:
            gc = gspread.service_account(filename=CREDENTIALS_FILE)
            sh = gc.open_by_url(PVME_SPREADSHEET)

            worksheet = sh.worksheet(worksheet)
        except FileNotFoundError as e:
            print(e)
        except Exception as e:
            print(e)
        else:
            return worksheet.get_all_values()

    @staticmethod
    def format_mkdocs_md(message):
        matches = [match for match in re.finditer(PVMESpreadSheet.PATTERN, message.content)]
        for match in reversed(matches):
            worksheet_data = PVMESpreadSheet.obtain_pvme_spreadsheet_data(match.group(1))
            row, column = a1_to_rowcol(match.group(2))
            if worksheet_data:
                price_formatted = "{}".format(worksheet_data[row-1][column-1])
            else:
                price_formatted = "N/A"

            message.content = message.content[:match.start()] + price_formatted + message.content[match.end():]
