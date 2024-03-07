import asyncio
import aiohttp
from bs4 import BeautifulSoup
import base64
from PIL import Image
from io import BytesIO
from pathlib import Path
import os

BASE_URL = "https://aip.dfs.de/BasicVFR/2024MAR07/chapter"
INDEX_PAGE = f"{BASE_URL}/3244a398014823f13ace4090907c74e3.html"
PRINT_URL = "https://aip.dfs.de/basicVFR/print"
FILENAME = "VFR_AIP.pdf"


def get_url(href):
    return BASE_URL + "/" + href


async def save_doc(session, url: str):
    headers = {"Referer": url}
    async with session.get(url, headers=headers) as response:
        print("Saving:", url)
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        img_el = soup.find("img")
        src = img_el.attrs.get("src").replace("data:image/png;base64,", "")
        decoded = base64.b64decode(src)

        image = Image.open(BytesIO(decoded))
        image.save(FILENAME, append=True)


async def save_part(session, url: str, print_url: str):
    async with session.get(url) as folder_response:
        folder_html = await folder_response.text()
        folder_soup = BeautifulSoup(folder_html, "html.parser")
        chapters = folder_soup.find_all("a", class_="folder-link")

        for chapter in chapters:
            async with session.get(
                get_url(chapter.attrs.get("href"))
            ) as chapter_response:
                chapter_html = await chapter_response.text()
            chapter_soup = BeautifulSoup(chapter_html, "html.parser")
            docs = chapter_soup.find_all("li", class_="document-item")
            for doc in docs:
                href = doc.find("a").attrs.get("href")
                doc_url = print_url + href.replace("../pages", "")
                await save_doc(session, doc_url)


async def main():
    if os.path.exists(FILENAME):
        os.remove(FILENAME)
    output_file = Path(FILENAME)
    output_file.touch()

    async with aiohttp.ClientSession() as session:
        async with session.get(INDEX_PAGE) as response:
            if not response.ok:
                print("Problem accessing index page")
            html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        gen_url = get_url(
            soup.find("span", string="GEN Allgemeine Information")
            .find_parent("a")
            .attrs.get("href")
        )
        enr_url = get_url(
            soup.find("span", string="ENR Streckeninformation")
            .find_parent("a")
            .attrs.get("href")
        )

        await save_part(session, gen_url, PRINT_URL + "/GEN")
        await save_part(session, enr_url, PRINT_URL + "/ENR")


asyncio.run(main())
