import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from urllib.parse import urlparse
import re # Regex for pattern matching


#Below are the patterns which can be changed based on the websites added later on

PRODUCT_PATH_PATTERNS = [
    r'/p/',
    r'/product/',
    r'/products/',
    r'/item/',
    r'/dp/', # Amazon
    r'/goods/', # Shein
    r'/[a-zA-Z0-9\-]+-p-\d+', # TataCliq has product names like /brand-name/p-MP000... or /categoy-separated-by-/p-M1234...
    # We will be using only these URLs for now and add more on observation
]


PRODUCT_PATH_REGEX = [re.compile(p, re.IGNORECASE) for p in PRODUCT_PATH_PATTERNS]
#using list comprehension for ease


LISTING_PATH_PATTERNS = [
    r'/c/', r'/category/', r'/categories/', r'/collections/', r'/shop/', r'/all/'
    # Add more patterns once observed
]


LISTING_PATH_REGEX = [re.compile(p, re.IGNORECASE) for p in LISTING_PATH_PATTERNS]