import os
import sys
import threading
import logging
import datetime
from collections import namedtuple
from functools import cached_property
from pathlib import Path
from pdfminer.high_level import extract_text

import bs4
import requests
from PyPDF2 import PdfFileMerger, PdfFileReader

# logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(asctime)-15s: %(message)s'))
logger.addHandler(ch)

Chapter = namedtuple('Chapter', ['order', 'url', 'filename'])


class Book:

    url: str = "http://pages.cs.wisc.edu/~remzi/OSTEP"
    book_url: str = f'{url}/'
    timeout: int = 180
    output_dir: str = './output'
    output_file: str = 'ostep.pdf'

    @property
    def hardcoded_chapters(self) -> [Chapter]:
        return [
            Chapter(1, "preface.pdf", "preface.pdf"),
            Chapter(2, "toc.pdf", "toc.pdf" ),
        ]

    @cached_property
    def index_page(self) -> str:
        logger.info('getting index page: %s ...', self.book_url)
        response = requests.get(self.book_url)
        response.raise_for_status()
        logger.info('getting index page: %s - done. response: %s',
            self.book_url, response)
        return response.text

    @cached_property
    def chapters(self) -> [Chapter]:
        logger.info('getting chapters ...')
        soup = bs4.BeautifulSoup(self.index_page, "html.parser")
        candidates = [s.parent for s in soup.select('td[bgcolor] > small')]
        logger.info('  ... candidates: %s', candidates)

        chapters = [
            Chapter(
                100 + int(s.find("small").text),
                s.find("a").attrs["href"],
                s.find("a").attrs["href"].replace('.pdf', '') + '.pdf'
            )
            for s in candidates
        ]
        result = sorted(self.hardcoded_chapters + chapters)
        logger.info('  ... result: %s', result)
        return result

    def download_chapters(self):
        logger.info('download chapters ...')
        def download(ch: Chapter):
            url = f'{self.url}/{ch.url}'
            logger.info(' ... downloading: %s', url)
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            if response.ok:
                file_name = f"{self.output_dir}/{ch.order:03d}-{ch.filename}"
                logger.info(' ... downloading: %s - done. saving into: %s',
                    url, file_name)
                with open(f"{file_name}", "wb") as f:
                    f.write(response.content)

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        threads = []
        for ch in self.chapters:
            t = threading.Thread(target=download, args=(ch,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
        logger.info('download chapters - done.')

    @property
    def downloaded_chapters(self) -> [Path]:
        return sorted(Path(self.output_dir).glob("*.pdf"))

    def get_title_from_pdf(self, idx: int, pdf: Path) -> str:
        # toc, preface have simple bookmark
        if idx in (0, 1):
            return pdf.stem.split('-')[1].capitalize()

        text = extract_text(str(pdf), maxpages=1)
        return '.'.join([t for t in text.split('\n')[:3] if t])

    def merge_chapters(self):
        logger.info('mering chapters ...')
        dt = datetime.datetime.now().strftime("%Y%m%d%H%M%S%z")

        merger = PdfFileMerger()
        merger.addMetadata({
            '/Author': 'Remzi Arpaci-Dusseau, Andrea Arpaci-Dusseau',
            '/Creator': 'Eugene Kalinin',
            '/Producer': 'https://github.com/ekalinin/ostep.py',
            '/Title': 'Operating Systems: Three Easy Pieces',
            '/CreationDate': dt,
            '/ModDate': dt,
        })
        for idx, pdf in enumerate(self.downloaded_chapters):
            bookmark = self.get_title_from_pdf(idx, pdf)
            logger.info(' ... idx=%d, pdf=%s, bookmark=%s', idx, pdf, bookmark)
            merger.append(open(pdf, 'rb'), bookmark=bookmark)

        with open(self.output_file, "wb") as book:
            merger.write(book)

        merger.close()
        logger.info('mering chapters - done. (%s)', self.output_file)

    def build(self):
        self.download_chapters()
        self.merge_chapters()


if __name__ == "__main__":
    Book().build()
