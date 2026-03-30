import pandas as pd
from bs4 import BeautifulSoup
import re, json, time, requests
from urllib.parse import urljoin

BASE_URL = "https://www.butlersystem.com"
SHOP_URL = "https://www.butlersystem.com/supply-division"

headers = {"User-Agent": "Mozilla/5.0"}

