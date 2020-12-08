import re
import sys
import requests


def generate_embed(link: str) -> str:
    """Obtain the html embed link from a raw (unparsed) link.

    :param link: raw unparsed (or pre-parsed from text) link
    :return: html formatted embed link (<a href="link">link</a> if no embed link is discovered)
    """
    # i.imgur (png) note: can be managed in else but about 90% of the links are in this format so it speeds up format
    if re.match(r"https?://i\.imgur\.com/([a-zA-Z0-9]+)\.png", link):
        embed = "<img class=\"media\" src=\"{}\">".format(link)

    # youtu.be
    elif match := re.match(r"https?://youtu\.be/([a-zA-Z0-9_\-]+)", link):
        embed = "<iframe class=\"media\" width=\"560\" height=\"315\" src=\"https://www.youtube.com/embed/{}\" frameborder=\"0\" allow=\"accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>".format(match.group(1))

    # youtube.com
    elif match := re.match(r"https?://(www\.)?youtube\.[a-z0-9.]*?/watch\?([0-9a-zA-Z$\-_.+!*'(),;/?:@=&#]*&)?v=([a-zA-Z0-9_\-]+)", link):
        embed = "<iframe class=\"media\" width=\"560\" height=\"315\" src=\"https://www.youtube.com/embed/{}\" frameborder=\"0\" allow=\"accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>".format(match.group(3))

    # clips.twitch.tv
    elif match := re.match(r"https?://clips\.twitch\.tv/([a-zA-Z]+)", link):
        # todo: embed not formatted correctly
        embed = "<iframe class=\"media\" src=\"https://clips.twitch.tv/embed?autoplay=false&clip={}\" frameborder=\"0\" allowfullscreen=\"true\" scrolling=\"no\" height=\"315\" width=\"560\"></iframe>".format(match.group(1))

    # twitch.tv/videos
    elif match := re.match(r"https?://www\.twitch\.tv/videos/([0-9a-zA-Z]+)", link):
        # todo: embed not formatted correctly
        embed = "<iframe class=\"media\" src=\"https://player.twitch.tv/?autoplay=false&video=v{}\" frameborder=\"0\" allowfullscreen=\"true\" scrolling=\"no\" height=\"335\" width=\"550\"></iframe>".format(match.group(1))

    # streamable
    elif match := re.match(r"https?://streamable.com/([a-zA-Z0-9]+)", link):
        embed = "<iframe class=\"media\" src=\"https://streamable.com/o/{}\" frameborder=\"0\" scrolling=\"no\" width=\"560\" height=\"315\" allowfullscreen></iframe>".format(match.group(1))

    else:
        # gyazo
        if re.match(r"https?://gyazo.com/([0-9a-fA-Z]+)", link):
            # todo: fetch api.gyazo.com to obtain the reformatted i.gyazo.com link
            adjusted_link = link

        # gfycat
        elif match := re.match(r"https?://gfycat\.com/([a-zA-Z0-9]+)", link):
            # todo: fetch api.gfycat.com to obtain the reformatted i.gyazo.com link
            adjusted_link = link

        # unknown link
        else:
            adjusted_link = link

        # obtain the type of embed from a request
        if adjusted_link.endswith(".gifv"):
            adjusted_link = re.sub(r"\.gifv$", ".mp4", adjusted_link)

        try:
            response = requests.head(adjusted_link)
            link_type = response.headers.get('content-type', '') if response.status_code == 200 else ''
        except requests.exceptions.RequestException:
            embed = "<a href=\"{}\">{}</a>".format(adjusted_link, adjusted_link)
        else:
            if link_type.startswith("image/"):
                embed = "<img class=\"media\" src=\"{}\">".format(adjusted_link)
            elif link_type.startswith("video/"):
                embed = "<video class=\"media\" autoplay loop muted controls><source src=\"{}\"></video>".format(adjusted_link)
            else:
                embed = "<a href=\"{}\">{}</a>".format(adjusted_link, adjusted_link)

    return embed


print(generate_embed("https://i.gyazo.com/a3b13b217022a8523de01b4e50b3cc9f.mp4"))
print(generate_embed("https://youtu.be/H-wtms5XHpI"))
print(generate_embed("https://www.youtube.com/watch?v=jpHp21Id-3g&feature=youtu.be"))
print(generate_embed("https://thumbs.gfycat.com/PartialSameIvorygull-size_restricted.gif"))
print(generate_embed("https://i.imgur.com/O63i4K2.png"))
print(generate_embed("https://i.imddgur.com/O63i4K2.png"))

# print(match)

