import logging
import webbrowser
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from time import sleep

import requests
from furl import furl
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from autobuy.autobuy_selenium import AutoBuy
from notifications.notifications import NotificationHandler

log = logging.getLogger(__name__)
formatter = logging.Formatter(
    "%(asctime)s : %(message)s : %(levelname)s -%(name)s", datefmt="%d%m%Y %I:%M:%S %p"
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
log.setLevel(10)
log.addHandler(handler)
DIGITAL_RIVER_OUT_OF_STOCK_MESSAGE = "PRODUCT_INVENTORY_OUT_OF_STOCK"
DIGITAL_RIVER_API_KEY = "9485fa7b159e42edb08a83bde0d83dia"
DIGITAL_RIVER_PRODUCT_LIST_URL = "https://api.digitalriver.com/v1/shoppers/me/products"
DIGITAL_RIVER_STOCK_CHECK_URL = "https://api.digitalriver.com/v1/shoppers/me/products/{product_id}/inventory-status?"
DIGITAL_RIVER_ADD_TO_CART_URL = (
    "https://api.digitalriver.com/v1/shoppers/me/carts/active/line-items"
)
DIGITAL_RIVER_CHECKOUT_URL = (
    "https://api.digitalriver.com/v1/shoppers/me/carts/active/web-checkout"
)

NVIDIA_CART_URL = "https://store.nvidia.com/store/nvidia/en_US/buy/productID.{product_id}/clearCart.yes/nextPage.QuickBuyCartPage"
NVIDIA_TOKEN_URL = "https://store.nvidia.com/store/nvidia/SessionToken"

GPU_DISPLAY_NAMES = {
    "2060S": "NVIDIA GEFORCE RTX 2060 SUPER",
    "3080": "NVIDIA GEFORCE RTX 3080",
    "3090": "NVIDIA GEFORCE RTX 3090",
}

ACCEPTED_LOCALES = [
    "en_us",
    "en_gb",
    "de_de",
    "fr_fr",
    "it_it",
    "es_es",
    "nl_nl",
    "sv_se",
    "de_at",
    "fr_be",
]

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36 Edg/85.0.564.51",
}
CART_SUCCESS_CODES = {201, requests.codes.ok}


class NvidiaBuyer:
    def __init__(self, gpu, locale="en_us"):
        self.product_ids = []
        self.cli_locale = locale.lower()
        self.locale = self.map_locales()
        self.session = requests.Session()
        self.gpu = gpu
        self.enabled = True
        try:
            self.gpu_long_name = GPU_DISPLAY_NAMES[gpu]
        except Exception as e:
            log.error("Invalid GPU name.")
            raise e

        adapter = HTTPAdapter(
            max_retries=Retry(
                total=10,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
            )
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.notification_handler = NotificationHandler()
        self.autobuy_handler = AutoBuy()


        log.info("Getting product IDs")
        self.get_product_ids()
        while len(self.product_ids) == 0:
            log.info(
                f"We have no product IDs for {self.gpu_long_name}, retrying until we get a product ID"
            )
            self.get_product_ids()
            sleep(5)

    def map_locales(self):
        if self.cli_locale == "de_at":
            return "de_de"
        if self.cli_locale == "fr_be":
            return "fr_fr"
        return self.cli_locale

    def get_product_ids(self, url=DIGITAL_RIVER_PRODUCT_LIST_URL):
        log.debug(f"Calling {url}")
        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "expand": "product",
            "fields": "product.id,product.displayName,product.pricing",
            "locale": self.locale,
        }
        headers = DEFAULT_HEADERS.copy()
        headers["locale"] = self.locale
        response = self.session.get(url, headers=headers, params=payload)

        log.debug(response.status_code)
        response_json = response.json()
        for product_obj in response_json["products"]["product"]:
            if product_obj["displayName"] == self.gpu_long_name:
                if self.check_if_locale_corresponds(product_obj["id"]):
                    self.product_ids.append(product_obj["id"])
        if response_json["products"].get("nextPage"):
            self.get_product_ids(url=response_json["products"]["nextPage"]["uri"])

    def run_items(self):
        log.info(
            f"We have {len(self.product_ids)} product IDs for {self.gpu_long_name}"
        )
        log.info(f"Product IDs: {self.product_ids}")
        with ThreadPoolExecutor(max_workers=len(self.product_ids)) as executor:
            [executor.submit(self.buy, product_id) for product_id in self.product_ids]

    def buy(self, product_id):
        log.info(
            f"Checking stock for {self.gpu_long_name} with product ID: {product_id}..."
        )
        cart_url = self.get_cart_url(product_id)
        while cart_url is None and self.enabled:
            log.debug(f"{self.gpu_long_name} with product ID: {product_id} not in stock.")
            sleep(5)
            cart_url = self.get_cart_url(product_id)

        log.info(f" {self.gpu_long_name} with product ID: {product_id} in stock: {cart_url}")
        self.notification_handler.send_notification(f" {self.gpu_long_name} with product ID: {product_id} in stock: {cart_url}")
        if self.autobuy_handler.enabled:
            log.info("Starting auto buy.")
            self.autobuy_handler.auto_buy(cart_url, self.locale)
            log.info("Auto buy complete.")
            self.enabled = False
        else:
            webbrowser.open_new(cart_url)
            log.info(f"Opened {cart_url}.")
            self.enabled = False

    def get_cart_url(self, product_id):
        access_token = self.get_nividia_access_token()

        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "format": "json",
            "method": "post",
            "productId": product_id,
            "locale": self.locale,
            "quantity": 1,
            "token": access_token,
            "_": datetime.now(),
        }
        log.debug(f"Adding {self.gpu_long_name} ({product_id}) to cart")
        response = self.session.get(
            DIGITAL_RIVER_ADD_TO_CART_URL, headers=DEFAULT_HEADERS, params=payload
        )
        log.debug(response.status_code)

        if response.status_code not in CART_SUCCESS_CODES:
            return

        log.debug(self.session.cookies)
        params = {"token": access_token}
        url = furl(DIGITAL_RIVER_CHECKOUT_URL).set(params)
        return url.url


    def check_if_locale_corresponds(self, product_id):
        special_locales = ["en_gb", "de_at", "de_de", "fr_fr", "fr_be"]
        if self.cli_locale in special_locales:
            url = f"{DIGITAL_RIVER_PRODUCT_LIST_URL}/{product_id}"
            log.debug(f"Calling {url}")
            payload = {
                "apiKey": DIGITAL_RIVER_API_KEY,
                "expand": "product",
                "locale": self.locale,
                "format": "json",
            }

            response = self.session.get(url, headers=DEFAULT_HEADERS, params=payload)
            log.debug(response.status_code)
            response_json = response.json()
            return self.cli_locale[3:].upper() in response_json["product"]["name"]
        return True

    def get_nividia_access_token(self):
        log.debug("Getting session token")
        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "format": "json",
            "locale": self.locale,
            "currency": "USD",
            "_": datetime.today(),
        }
        response = self.session.get(
            NVIDIA_TOKEN_URL, headers=DEFAULT_HEADERS, params=payload
        )
        log.debug(response.status_code)
        return response.json()["access_token"]
