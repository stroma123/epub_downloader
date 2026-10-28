import json
from urllib.parse import urlparse
import re
import cloudscraper
from bs4 import BeautifulSoup, Tag

from src.epub_locator.epub_handler import EpubHandler


class EpubPubHandler(EpubHandler):
    def get_epub_base_url(self) -> str:
        domain = urlparse(self.url).netloc
        if domain == "continuous.epub.pub":
            scraper = cloudscraper.create_scraper()
            response = scraper.get(self.url)
            response.raise_for_status()

            match = re.search(
                r'https://asset\.epub\.pub/epub/[^"\\\s]+?\.epub/',
                response.text,
            )
            if not match:
                raise RuntimeError(
                    "Failed to find EPUB base URL in the continuous page."
                )

            epub_base_url = match.group(0).rstrip("/")
            self.ebook_name = (
                epub_base_url.rsplit("/", 1)[-1].removesuffix(".epub")
            )
        elif domain == "spread.epub.pub":
            content_opf_url = self._get_epub_pub_ebook_content_opf_url(self.url)
            epub_base_url = self._get_epub_base_url_from_specific_url(content_opf_url)
        elif domain == "asset.epub.pub":
            epub_base_url = self._get_epub_base_url_from_specific_url(self.url)
        else:
            content_opf_url = self._get_epub_pub_read_online_opf_url()
            epub_base_url = self._get_epub_base_url_from_specific_url(content_opf_url)

        self.logster.log(f"Determined EPUB base URL: {epub_base_url}")
        return epub_base_url

    def _get_epub_base_url_from_specific_url(self, url) -> str:
        self.logster.log(f"Parsing base url from url {url}")
        parts: list[str] = url.split("/")
        epub_base_url_parts: list[str] = []

        for part in parts:
            epub_base_url_parts.append(part)
            if part.endswith(".epub"):
                self.ebook_name = part.split(".")[0]
                break

        return "/".join(epub_base_url_parts)

    def _get_epub_pub_read_online_opf_url(self) -> str:
        self.logster.log(f"Fetching read online link from url {self.url}")
        scraper = cloudscraper.create_scraper()
        response = scraper.get(self.url)
        response.raise_for_status()
        # Extract fullUrl from staticAsset
        full_url_pattern = r'\\"fullUrl\\":\s*\\"([^\\]+)\\"'
        full_url_match = re.search(full_url_pattern, response.text)
        if not full_url_match:
            raise RuntimeError("Failed to find fullUrl in the page.")

        # Extract packageOpfPath
        package_opf_pattern = r'\\"packageOpfPath\\":\s*\\"([^\\]+)\\"'
        package_opf_match = re.search(package_opf_pattern, response.text)

        if not package_opf_match:
            raise RuntimeError("Failed to find packageOpfPath in the page.")

        read_online_url: str = f"https://asset.epub.pub/epub{full_url_match.group(1)}/{package_opf_match.group(1)}"
        return read_online_url

    def _get_epub_pub_ebook_content_opf_url(self, read_online_url: str) -> str:
        self.logster.log(f"Fetching content.opf from url {read_online_url}")
        scraper = cloudscraper.create_scraper()
        response = scraper.get(read_online_url)
        response.raise_for_status()

        # The current spread.epub.pub page embeds the asset URL
        # in Next.js serialized page data.
        match = re.search(
            r'https://asset\.epub\.pub/[^"\\\s]*?\.epub/[^"\\\s]*\.opf',
            response.text,
        )

        if match:
            asset_url = match.group(0)
            self.logster.log(f"Found content.opf URL: {asset_url}")
            return asset_url

        raise RuntimeError(
            "Failed to find content.opf URL in the spread page. "
            "The page format may have changed or access may be blocked."
        )

