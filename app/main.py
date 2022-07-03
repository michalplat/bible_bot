import os
import httpx
import interactions
import json
import logging

import pydantic
from rich.console import Console
from rich import table
from typing import Dict, List, Tuple, Union
from lexicon import AliasDict
from app.help import help_msg
from app.models import Verses
from app.deutertocanonical import DEUT_SET, get_table

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

ALL_APOCRYFS = get_table()
deut_set = {"1ES", "2ES", "TOB", "JDT", "ESG", "WIS", "SIR", "BAR", "S3Y", "SUS", "BEL", "MAN", '1MA', "2MA"}
bot = interactions.Client(os.getenv('BOT_TOKEN'))
UBG = "Uwspółcześniona Biblia Gdańska"
KJV = "Kings James Version"
LIT = "Literal Standard Version"
CKB = "Czech Kralická Bible 1613"

# load available translations
with open("/app/data/translations.json", encoding="utf-8") as trans:
    translations = json.load(trans)

# load available references
with open("/app/data/references.json", encoding="utf-8") as refs:
    refs_data = json.load(refs)

books_and_chapters = httpx.get("https://api.scripture.api.bible/v1/bibles/{0}/books?include-chapters=true".format(translations[UBG]),
                               headers={"api-key": os.getenv("BIBLE_API_TOKEN")})


# create alias dict to use aliases of books
bible_references = AliasDict()
all_books: Dict[str, Tuple[str, int]] = dict()
for book in books_and_chapters.json()["data"]:
    fullname = book["nameLong"]
    key = book["id"].title()
    key_l = key.lower()
    bible_references[key_l] = key
    bible_references.alias(from_=fullname, to=key_l)
    all_books[key] = (fullname, len(book["chapters"])-1)
    for alias in refs_data[key]["aliases"].split(", "):
        bible_references.alias(from_=alias, to=key_l)
        bible_references.alias(from_=alias.lower(), to=key_l)


def get_rich_output(rich_object):
    console = Console(width=50)
    with console.capture() as capture:
        console.print(rich_object)
    return capture.get()


async def split_data(data: str) -> List[str]:
    """
    Split data for chunks of maximally 2000 chars allowed by discord.
    """
    # get end of the verse the closest to the 2000. char.
    chunks: List[str] = []
    try:
        where_to_split = data.index("[", 1800, 1999)
    except ValueError:
        logger.debug("No end of the verse found between 1800 and 1999 char. Trying between 1000 and 1999.")
        where_to_split = data.index("[", 1000, 1999)  # The longest verse in the bible has less than 450 chars. We should be safe here.
    single_chunk = data[:where_to_split]
    chunks.append(single_chunk)
    new_data = data[where_to_split:]
    if len(new_data) >= 2000:
        chunks.extend(await split_data(new_data))
    else:
        chunks.append(new_data)
    return chunks


def get_verses_from_api(book: str, chapter: int, verses: Verses, translation: str = "UBG") -> Union[httpx.Response, str]:
    response = httpx.get("https://api.scripture.api.bible/v1/bibles/{0}/verses/{1}.{2}.{3}-{1}.{2}.{4}?content-type=text".
                         format(translations[translation], book, chapter, verses.from_verse, verses.to_verse),
                         headers={"api-key": os.getenv("BIBLE_API_TOKEN")})
    if response.is_error:
        return response
    json_data = response.json()
    logger.debug(json_data)
    return json_data["data"]["content"]


def get_number_of_verses_from_api(book: str, chapter: int, translation: str) -> Union[httpx.Response, int]:
    response = httpx.get("https://api.scripture.api.bible/v1/bibles/{0}/chapters/{1}.{2}/verses?content-type=text".format(translations[translation], book, chapter),
                         headers={"api-key": os.getenv("BIBLE_API_TOKEN")})
    if response.is_error:
        return response
    json_data = response.json()
    logger.debug("Fetched verses: %s", json_data["data"])
    return len(json_data["data"])


def search_using_api(search_phrase: str, fuzziness: int, translation: str) -> Union[httpx.Response, str]:
    response = httpx.get("https://api.scripture.api.bible/v1/bibles/{0}/search?query={1}&fuzziness={2}"
                         .format(translations[translation], search_phrase, fuzziness),
                         headers={"api-key": os.getenv("BIBLE_API_TOKEN")})
    if response.is_error:
        return response
    data = response.json()["data"]
    verses = "Brak wyników, spróbuj innej frazy." if not data["verses"] else "\n\n".join(f"`{match['reference']}:`\n {match['text']}"
                                                                                       for match in data["verses"])
    return f"Wyniki dla wyszukiwania `'{data['query']}'`, {translation}:\n\n{verses}"


def send_request_to_api_and_verify_output(book: str, chapter: int, verses: Verses, translation: str):
    api_book = bible_references[book.lower()]
    api_verses = get_verses_from_api(api_book, chapter, verses, translation)
    if isinstance(api_verses, httpx.Response):
        logger.debug("Api wrong response is: %s", api_verses.content)
        if api_verses.status_code == 404:
            verses_count = get_number_of_verses_from_api(api_book, chapter, translation)
            if isinstance(verses_count, httpx.Response) and verses_count.status_code == 404:
                return "Coś poszło nie tak. Zagadaj do `michalplat`."

            verses_form = "wersy" if verses_count % 10 in {2, 3, 4} else "wers" if verses_count == 1 else "wersów"
            return f"Podano nieistniejący zakres wersów: `{verses.repr_verses}`. Rozdział nr. `{chapter}` księgi o nazwie " \
                   f"`{all_books[api_book][0]}` ma tylko `{verses_count}` {verses_form}."
        else:
            return "Coś poszło nie tak. Zagadaj do `michalplat`."
    else:
        return f"**`{all_books.get(api_book, (book.title(),))[0]} {chapter}, {verses.repr_verses}, {translation}:`**\n ```{api_verses}```"


def get_verses(book: str, chapter: int, verses: Verses, translation: str):

    if book in bible_references:
        book_name, chapters_count = all_books[bible_references[book]]
        if chapter > chapters_count:
            chapters_form = "rozdziały" if chapters_count % 10 in {2, 3, 4} else "rozdział" if chapters_count == 1 else "rozdziałów"
            return f"Nie ma rozdziału o numerze `{chapter}` w księdze o nazwie: `{book_name}`, która zawiera tylko `{chapters_count}`" \
                   f" {chapters_form}."

        return send_request_to_api_and_verify_output(book, chapter, verses, translation)

    elif book in DEUT_SET.keys():
        translation = "KJV"
        text = f"Księga {book.upper()} nie istnieje w podanym przez Ciebie tłumaczeniu," \
               f" ale istnieje w King James Version (księga deuterokanoniczna):\n\n"

        return text + send_request_to_api_and_verify_output(book, chapter, verses, translation)

    else:
        return f"Księga {book.upper()} nie istnieje w zbiorach kanonicznych ani deuterokanonicznych, spróbuj wpisać innną księgę."


# log message on hello
@bot.event
async def on_ready():
    print(f'We have logged in as {bot.me.name}')


@bot.command(name="biblia_pomoc", description="Podstawowe informacje o tym jak gadać z Panią Biblią.")
async def pomoc_biblia(ctx: interactions.CommandContext):
    await ctx.send(help_msg)


@bot.command(name="apokryfy",  description="Księgi deutrokanoniczne? Dalej nic? Nooo, te co Jezus nie czytał, a katolicy czytają.")
async def deut(ctx: interactions.CommandContext):
    await ctx.send(f"```{get_rich_output(ALL_APOCRYFS)}```")


@bot.command(name="szukaj",
             description="Wyszukiwanie w Biblii wybranego słowa/frazy.",
             options=[
                 interactions.Option(
                     name="szukam",
                     description="Tekst, który chcesz znaleźć. Może być słowo, może być coś więcej. Spróbuj!",
                     type=interactions.OptionType.STRING,
                     required=True,
                 ),
                 interactions.Option(
                     name="dokladnosc",
                     description="Wybierz jak dokładnie chcesz szukać.",
                     type=interactions.OptionType.INTEGER,
                     choices=[
                         interactions.Choice(name="Szukam dokładnie", value=0),
                         interactions.Choice(name="Nie jestem pewny czego szukam", value=1),
                         interactions.Choice(name="Nie mam pojęcia czego szukam", value=2),
                     ],
                     required=False,
                 ),
                 interactions.Option(
                     name="tlumaczenie",
                     description="Tłumaczenie biblii które chcesz użyć do wyszukiwania.",
                     type=interactions.OptionType.STRING,
                     choices=[
                         interactions.Choice(name=UBG, value=UBG),
                         interactions.Choice(name=KJV, value=KJV),
                         interactions.Choice(name=LIT, value=LIT),
                         interactions.Choice(name=CKB, value=CKB),
                     ],
                     required=False,
                 ),
             ],
             )
async def szukaj(ctx: interactions.CommandContext, szukam: str, dokladnosc: int, tlumaczenie: str):
        data = search_using_api(szukam, dokladnosc, tlumaczenie)
        if isinstance(data, httpx.Response):
            logger.debug(data.json())
            await ctx.send("Coś poszło nie tak. Zagadaj do `michalplat`.")
        logger.debug("Length of the data: %s", data)
        await ctx.send(data)


@bot.command(name="ksiegi",
             description="Wypisze podstawowe skróty i informacje o księgach Starego i Nowego Testamentu.",
             )
async def ksiegi(ctx: interactions.CommandContext) -> None:
    books_table: table.Table = table.Table(show_lines=True, title="Wszystkie Księgi")
    books_table.add_column("Skrót")
    books_table.add_column("Nazwa")
    books_table.add_column("Rozdziały")
    all_books_length = len(all_books)
    for index, (book_ref, (book_fullname, chapters_number)) in enumerate(all_books.items(), 1):
        books_table.add_row(book_ref, book_fullname, str(chapters_number))
        if index == all_books_length or index % (all_books_length//4 + 1) == 0:
            data = get_rich_output(books_table)
            await ctx.send(f"```{data}```")
            books_table.rows = []
            books_table.columns[0]._cells = []
            books_table.columns[1]._cells = []
            books_table.columns[2]._cells = []


@bot.command(name="skroty",
             description="Wypisze alternatywne skróty podanej księgi.",
             options=[
                 interactions.Option(
                     name="ksiega",
                     description="Nazwa księgi której aliasy (skróty) chcesz zobaczyć.",
                     type=interactions.OptionType.STRING,
                     required=True,
                 ),
             ],
             )
async def skroty(ctx: interactions.CommandContext, ksiega: str):
    ksiega_l = ksiega.lower()
    if ksiega_l in bible_references:
        await ctx.send(", ".join(bible_references.aliases_of(ksiega_l) + [ksiega_l]))
    else:
        await ctx.send(f"Nie ma takiej księgi jak **{ksiega}**.")


@bot.command(name="wersy",
             description="Wyciągarka wersów.",
             options=[
                 interactions.Option(
                     name="ksiega",
                     description="Nazwa księgi lub skrót (/ksiegi i /skroty mogą być tutaj przydatne).",
                     type=interactions.OptionType.STRING,
                     required=True,
                 ),
                 interactions.Option(
                     name="rozdzial",
                     description="Numer rozdziału.",
                     type=interactions.OptionType.INTEGER,
                     required=True,
                 ),
                 interactions.Option(
                     name="wersy",
                     description="Jeden wers lub zakres wersów, np. 1-15 lub 7.",
                     type=interactions.OptionType.STRING,
                     required=True,
                 ),
                 interactions.Option(
                     name="tlumaczenie",
                     description="Tłumaczenie biblii które chcesz.",
                     type=interactions.OptionType.STRING,
                     choices=[
                         interactions.Choice(name=UBG, value=UBG),
                         interactions.Choice(name=KJV, value=KJV),
                         interactions.Choice(name=LIT, value=LIT),
                         interactions.Choice(name=CKB, value=CKB),
                     ],
                     required=False,
                 ),
             ],
             )
async def wersy(ctx: interactions.CommandContext, ksiega: str, rozdzial: int, wersy: str, tlumaczenie: str = "Uwspółcześniona Biblia Gdańska"):
    try:
        wersy = Verses(user_input=wersy)
        data = get_verses(ksiega.lower(), rozdzial, wersy, tlumaczenie)
        if len(data) >= 2000:
            data_chunks = await split_data(data)
            last_chunk = len(data_chunks)
            for chunk_number, chunk in enumerate(data_chunks, 1):
                if chunk_number == last_chunk:
                    sentence = f"```{chunk}"
                elif chunk_number == 1:
                    sentence = f"{chunk.rstrip()}```"
                else:
                    sentence = f"```{chunk.rstrip()}```"
                logger.debug("Sentence length %s", len(sentence))
                await ctx.send(f"{sentence}")
        else:
            await ctx.send(data)
    except pydantic.ValidationError as err:
        logger.info("Verses validation error: %s", err)
        await ctx.send(f"Źle podane wersy, ma być **numerek1-numerek2** albo sam **numerek**, no i **numerek1** musi być mniejszy niż **numerek2**, "
                       f"a podane zostało: **`{wersy}`**.")


bot.start()
