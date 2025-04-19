import json
import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from urllib.parse import urljoin, urlparse
import re
from ecom_crawler.items import ProductItem
from w3lib.url import canonicalize_url
import logging
logger = logging.getLogger(__name__)
from scrapy_playwright.page import PageMethod

PRODUCT_PATH_PATTERNS = [
    r'/p/', r'/product/', r'/products/[^/]+', r'/products/',
    r'/.*/p-[^/]+$',#for tatacliq
    r'/item/', r'/dp/', r'/goods/',
    r'/[a-zA-Z0-9\-]+-p-\d+',
    r'https?://(?:www\.)?westside\.com/products/[^/?#]+',
    r'https?://(?:www\.)?tatacliq\.com/products/[^/?#]+',
    r'https?://(?:www\.)?nykaafashion\.com/products/[^/?#]+',
    r'https?://(?:www\.)?virgio\.com/products/[^/?#]+',
]

PRODUCT_PATH_REGEX = [re.compile(p, re.IGNORECASE) for p in PRODUCT_PATH_PATTERNS]

LISTING_PATH_PATTERNS = [
    r'/c/', r'/category/', r'/categories/', r'/collections/', r'/shop/', r'/all/',  r'/.*/c-[^/]+$'
]
LISTING_PATH_REGEX = [re.compile(p, re.IGNORECASE) for p in LISTING_PATH_PATTERNS]

PATHS_CONTAINING_PRODUCTS_IN_SCRIPTS_PATTERNS = [r'/collections/']

PATHS_CONTAINING_PRODUCTS_IN_SCRIPTS_REGEX = [re.compile(p, re.IGNORECASE) for p in PATHS_CONTAINING_PRODUCTS_IN_SCRIPTS_PATTERNS]

ADD_TO_CART_SELECTORS = [
    'button[id*="add-to-cart"]',
    'button[class*="add-to-cart"]',
    'button[data-action*="add-to-cart"]',
    'input[type="submit"][value*="Add to Cart"]',
    'button:contains("Add to Bag")', 
    'button:contains("Buy Now")',
    'form[action*="cart/add"]'
]
PRICE_SELECTORS = [
    '[class*="price"]', '[id*="price"]',
    '[itemprop="price"]',
    '.product-price', '.Price--final', '.selling-price' # Add site-specific ones
]
PRODUCT_SCHEMA_SELECTOR = '[itemtype*="schema.org/Product"]'


class EcomProductSpider(CrawlSpider):
    name = 'ecom_product_spider'

    #uncomment below to test out anything
    # def start_requests(self):
    #   for domain in self.allowed_domains:
    #       if domain == "tatacliq.com":
    #           yield scrapy.Request(
    #               url="https://www.tatacliq.com/womens-clothing/c-msh1014",
    #               callback=self.parse_page,
    #               meta={"playwright": True}
    #           )
    # Input domains will be passed via the command line
    # scrapy crawl ecom_product_spider -a domains="virgio.com,westside.com,tatacliq.com,nykaafashion.com" 
    # run above command to run on all 4 mentioned domains
    # add -s LOG_FILE=log.txt -s LOG_LEVEL=INFO at the end to check the logs from the log file and find denyable URL patterns

    def __init__(self, *args, **kwargs):
        # Get domains from command line argument, split by comma
        self.domains_input = kwargs.pop('domains', '').split(',')
        self.allowed_domains = [d.strip() for d in self.domains_input if d.strip()]
        self.start_urls = [f"https://{d}" for d in self.allowed_domains]
        self.visited_collections = set()

        # We will be using Playwright to access JS-rendered links but we want to make sure to use this only for websites that have js-rendered product links
        self.JS_RENDERED_DOMAINS = ["https://www.westside.com", "https://www.tatacliq.com"]        
        if not self.allowed_domains:
            raise ValueError("No domains provided. Use -a domains='domain1.com,domain2.com'")

        # --- Scrapy CrawlSpider Rules ---
        EcomProductSpider.rules = (
            Rule(
                LinkExtractor(
                    allow_domains=self.allowed_domains,
                    # Deny common non-product/non-category paths and more to come from logs of different sites on observation
                    deny=(
                        r'/customer/', r'/account/', r'/login', r'/cart', r'/checkout',
                        r'/policy', r'/terms', r'/about', r'/contact', r'/apps/buy/',
                        r'\.jpg$', r'\.png$', r'\.pdf$', r'\.css$', r'\.js$' # File types
                    ),
                    canonicalize=True, 
                    unique=True
                ),
                callback='parse_page', 
                follow=True # Keep following links from the followed pages
            ),
            # Rule 2 (Very useful): Explicitly target sitemaps
            Rule(
                LinkExtractor(allow=(r'sitemap.*\.xml',), allow_domains=self.allowed_domains),
                callback='parse_sitemap',
                # follow=True
            ),
        )
        super(EcomProductSpider, self).__init__(*args, **kwargs)
        self.logger.info(f"Starting crawl for domains: {self.allowed_domains}")
        self.found_products = {domain: set() for domain in self.allowed_domains} # Track unique URLs per domain


    # Override _parse_response to implement custom logic before rules are applied
    # Or simply use parse_page as the primary callback
    def parse_page(self, response):
        """
        Primary callback for processing downloaded pages.
        Decides if a page is a product page or just contains links to follow.
        """
        self.logger.debug(f"Parsing page: {response.url}")
        is_potential_collection_page = any(regex.search(response.url) for regex in LISTING_PATH_REGEX)
        if is_potential_collection_page and any(response.url.startswith(domain) for domain in self.JS_RENDERED_DOMAINS) and response.url not in self.visited_collections:
          self.logger.debug(f"Going for Playwright crawling in URL: {response.url}")
          self.visited_collections.add(response.url)
          req = scrapy.Request(
            response.url,
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", 'a[href*="/p-"], a[href*="/product/"], a[href*="/products/"], a[href*="productId"]', timeout=5000)
                ],
                "playwright_context": "default",
            },
            dont_filter=True,
            callback=self.parse_collections_playwright
        )
          self.logger.debug(f"Yielding Playwright request for: {response.url}")
          yield req

        # Check 1: Check URL Pattern against the product pattern defined earlier
        is_potential_product_by_url = any(regex.search(response.url) for regex in PRODUCT_PATH_REGEX)

        # Check 2: HTML Content Analysis (if potentially product or unknown)
        is_confirmed_product_by_html = False
        if is_potential_product_by_url or not any(regex.search(response.url) for regex in LISTING_PATH_REGEX): # If URL looks like product OR not clearly a listing page
             if self.is_product_page(response):
                  is_confirmed_product_by_html = True

        # Decision: Yield item if confirmed product
        if is_confirmed_product_by_html:
          domain = urlparse(response.url).netloc.replace('www.', '')
          if domain not in self.found_products:
            self.logger.warning(f"Domain {domain} from URL {response.url} not in tracked domains.")
            return  # good practice to early return to reduce nesting 

          # Check uniqueness before yielding
          canonical_url = canonicalize_url(response.url)

          if canonical_url in self.found_products[domain]:
              self.logger.debug(f"Duplicate product item skipped: {response.url}")
              return

          self.logger.info(f"Found product: {response.url}")
          item = ProductItem()
          item['domain'] = domain
          item['url'] = response.url
          self.found_products[domain].add(canonical_url)
          yield item

    def extract_json_ld_product(self, response):
      """
      Checks if the page contains JSON-LD structured data indicating a Product.
      """
      scripts = response.css('script[type="application/ld+json"]::text').getall()
      for script in scripts:
          try:
              data = json.loads(script)
              # Handle both list and dict JSON-LD formats
              if isinstance(data, list):
                  for entry in data:
                      if isinstance(entry, dict) and entry.get('@type') == 'Product':
                          self.logger.debug(f"JSON-LD Product found on {response.url}")
                          return True
              elif isinstance(data, dict) and data.get('@type') == 'Product':
                  self.logger.debug(f"JSON-LD Product found on {response.url}")
                  return True
          except json.JSONDecodeError:
              continue
      return False
    
    def is_product_page(self, response):
        """
        Analyzes HTML content to determine if it's likely a product page.
        Returns True if indicators are found, False otherwise.
        """
        # Check for Schema.org Product markup (strong indicator)
        if response.css(PRODUCT_SCHEMA_SELECTOR):
            self.logger.debug(f"Product Schema found on {response.url}")
            return True

        if self.extract_json_ld_product(response):
          return True
        # Check for "Add to Cart" button (strong indicator) => most likely to contain product link
        for selector in ADD_TO_CART_SELECTORS:
             # Handle :contains pseudo-class if needed (requires specific setup or library update)
            if ":contains" in selector:
                # Requires parsel >= 1.7 or custom implementation
                element_text = selector.split(':contains(')[1].strip(')"\'')
                button_selector = selector.split(':contains(')[0]
                if response.css(button_selector).xpath(f'.//text()[contains(., "{element_text}")]'):
                    self.logger.debug(f"Add to Cart text match found on {response.url} with {selector}")
                    return True
            elif response.css(selector):
                self.logger.debug(f"Add to Cart selector match found on {response.url} with {selector}")
                return True

        # Check for price element (medium indicator - can be on listing pages too)
        # Combine with other checks for better accuracy
        has_price = False
        for selector in PRICE_SELECTORS:
            if response.css(selector):
                has_price = True
                break

        h1_text = response.css('h1::text').get()
        # Simple check: title exists and isn't too generic like "Search Results"
        has_plausible_title = h1_text and len(h1_text.split()) > 1 and len(h1_text.split()) < 15

        # Combine weaker indicators (e.g., price AND plausible title)
        if has_price and has_plausible_title:
             self.logger.debug(f"Price and plausible title found on {response.url}")
             return True

        # If none of the strong indicators match, assume not a product page
        self.logger.debug(f"No definitive product indicators found on {response.url}")
        return False

    def parse_sitemap(self, response):
        """
        Parses XML sitemaps (if found by the rule).
        Yields requests for URLs found within the sitemap.
        """
        self.logger.info(f"Parsing sitemap: {response.url}")
        sitemap = scrapy.utils.sitemap.Sitemap(response.body)
        for entry in sitemap:
            url = entry['loc']       
            yield scrapy.Request(url, callback=self.parse_page)

    def parse_collections_playwright(self,response):
        self.logger.info(f"Parsing collection page: {response.url}")

        # Select all product anchor tags
        product_links = response.css('a[href*="/p-"], a[href*="/product/"], a[href*="/products/"], a[href*="productId"]')
        product_links = [a.attrib['href'] for a in product_links if 'href' in a.attrib]
        if not product_links:
            self.logger.warning(f"No product links found on {response.url}")
            return
        for link in product_links:
            if link not in self.visited_collections:    
              abs_url = response.urljoin(link)
              self.logger.info(f"Found product link: {abs_url}")
              is_potential_collection_page = any(regex.search(abs_url) for regex in LISTING_PATH_REGEX)
              if is_potential_collection_page and abs_url not in self.visited_collections:
                self.visited_collections.add(abs_url)
                self.logger.debug(f"Yielding Playwright request for: {response.url}")
                yield scrapy.Request(
                  response.url,
                  meta={
                      "playwright": True,
                      "playwright_page_methods": [
                          PageMethod("wait_for_selector", 'a[href*="/p-"], a[href*="/product/"], a[href*="/products/"], a[href*="productId"]',timeout=5000)
                      ],
                      "playwright_context": "default",
                  },
                  dont_filter=True,
                  callback=self.parse_collections_playwright
                  )
              else:
                  yield scrapy.Request(
                  abs_url,
                  callback=self.parse_page
              )
            