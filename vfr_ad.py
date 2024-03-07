import asyncio
import aiohttp
import os
import shutil
from bs4 import BeautifulSoup
import base64
from PIL import Image
from io import BytesIO


OUTPUT_DIR = "output"
BYOP_DIR = f"{OUTPUT_DIR}/byop"
BASE_URL = "https://aip.dfs.de/BasicVFR/2024MAR07/chapter"
INDEX_PAGE = f"{BASE_URL}/dc740af5fe2e7014197f8b8433ff6926.html"
PRINT_URL = "https://aip.dfs.de/basicVFR/print/AD"

LINK_SELECTOR = "a.folder-link[href]"
NAME_SELECTOR = 'span.folder-name[lang="en"]'


async def save_doc(session, url: str, name: str):
    filename = name.replace(" ", "_VFR-AIP_", 1)

    headers = {"Referer": url}
    async with session.get(url, headers=headers) as response:
        print("Saving:", filename)
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        img_el = soup.find("img")
        src = img_el.attrs.get("src").replace("data:image/png;base64,", "")
        decoded = base64.b64decode(src)

        image = Image.open(BytesIO(decoded))
        image.save(BYOP_DIR + "/" + filename + ".pdf")


async def main():
    os.makedirs(BYOP_DIR, exist_ok=True)
    shutil.copy2("./manifest.json", OUTPUT_DIR + "/")

    async with aiohttp.ClientSession() as session:
        async with session.get(INDEX_PAGE) as response:
            if not response.ok:
                print("Problem accessing index page")
            html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        folders = soup.find_all("a", class_="folder-link")

        for folder in folders[3:]:
            folder_url = BASE_URL + "/" + folder.attrs.get("href")
            async with session.get(folder_url) as folder_response:
                if not folder_response.ok:
                    continue
                folder_html = await folder_response.text()
            folder_soup = BeautifulSoup(folder_html, "html.parser")
            airfields = folder_soup.find_all("a", class_="folder-link")

            for airfield in airfields:
                airfield_url = BASE_URL + "/" + airfield.attrs.get("href")
                print("Airfield", airfield_url)
                async with session.get(airfield_url) as airfield_response:
                    if not airfield_response.ok:
                        continue
                    airfield_html = await airfield_response.text()
                airfield_soup = BeautifulSoup(airfield_html, "html.parser")
                docs = airfield_soup.find_all("li", class_="document-item")

                doc_tasks = []
                airfield_name = airfield.find("span", lang="en").get_text().split()[-1]

                for doc in docs:
                    href = doc.find("a").attrs.get("href")
                    name = doc.find("span", lang="en").get_text()
                    folder_url = PRINT_URL + href.replace("../pages", "")
                    if name.startswith("AD"):
                        task = asyncio.ensure_future(
                            save_doc(
                                session, folder_url, airfield_name + "_VFR-AIP_Info"
                            )
                        )
                    else:
                        task = asyncio.ensure_future(
                            save_doc(session, folder_url, name)
                        )
                    doc_tasks.append(task)
                await asyncio.gather(*doc_tasks)

    print("Compressing archive...")
    shutil.make_archive("charts", "zip", OUTPUT_DIR)


asyncio.run(main())
