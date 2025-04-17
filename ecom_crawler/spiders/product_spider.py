import json
import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from urllib.parse import urlparse
import re # Regex for pattern matching
from ecom_crawler.items import ProductItem

#Below are the patterns which can be changed based on the websites added later on

PRODUCT_PATH_PATTERNS = [
    r'/p/',
    r'/product/',
    r'/products/[^/]+',
    r'https?://(?:www\.)?westside\.com/products/[^/?#]+',
    r'https?://(?:www\.)?tatacliq\.com/products/[^/?#]+',
    r'https?://(?:www\.)?nykaafashion\.com/products/[^/?#]+',
    r'https?://(?:www\.)?virgio\.com/products/[^/?#]+',
    r'/products/',
    r'/item/',
    r'/dp/', 
    r'/goods/', 
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

# --- Heuristics for HTML Analysis ---
# Simple checks, can be made more robust (e.g., checking text content)
ADD_TO_CART_SELECTORS = [
    'button[id*="add-to-cart"]',
    'button[class*="add-to-cart"]',
    'button[data-action*="add-to-cart"]',
    'input[type="submit"][value*="Add to Cart"]',
    'button:contains("Add to Bag")', # Requires parsel >= 1.7
    'button:contains("Buy Now")',
    'form[action*="cart/add"]'
]
PRICE_SELECTORS = [
    '[class*="price"]', '[id*="price"]',
    '[itemprop="price"]',
    '.product-price', '.Price--final', '.selling-price' # Add site-specific ones
]
PRODUCT_SCHEMA_SELECTOR = '[itemtype*="schema.org/Product"]' # Microdata
# Note: JSON-LD requires parsing <script> tags, more complex

class EcomProductSpider(CrawlSpider):
    name = 'ecom_product_spider'
  
    # Input domains will be passed via the command line
    # scrapy crawl ecom_product_spider -a domains="virgio.com,tatacliq.com,nykaafashion.com,westside.com" 
    # run above command to run on all 4 mentioned domains
    # add -s LOG_FILE=log.txt -s LOG_LEVEL=INFO at the end to check the logs from the log file and find denyable URL patterns



    def __init__(self, *args, **kwargs):
        # Domains should be passed via the command line and should be separated by , only
        # We will split them by comma
        self.domains_input = kwargs.pop('domains', '').split(',')
        self.allowed_domains = [d.strip() for d in self.domains_input if d.strip()]
        self.start_urls = [f"https://{d}" for d in self.allowed_domains]

        if not self.allowed_domains:
            raise ValueError("No domains provided. Please Use -a domains='domain1.com,....'")

        # --- Scrapy CrawlSpider Rules ---
        EcomProductSpider.rules = (
            # Rule 1: Follow links that are likely category/listing pages or potentially product pages
            Rule(
                LinkExtractor(
                    allow_domains=self.allowed_domains,
                    # Deny common non-product/non-category paths
                    # Find patterns from logs to reduce runtime
                    deny=(
                        r'/customer/', r'/account/', r'/login', r'/cart', r'/checkout',
                        r'/policy', r'/terms', r'/about', r'/contact',r'/apps/buy/',r'/blogs/'
                        r'\.jpg$', r'\.png$', r'\.pdf$', r'\.css$', r'\.js$',
                    ),
                    canonicalize=True, # Important for duplicate filtering
                    unique=True
                ),
                callback='parse_page', # Changed from default 'parse_item'
                follow=True # Keep following links from followed pages
            ),
            # Rule 2 (Optional but potentially useful): Explicitly target sitemaps
            Rule(
                LinkExtractor(allow=(r'sitemap.*\.xml',), allow_domains=self.allowed_domains),
                callback='parse_sitemap'
                # 'follow=False' as sitemaps typically link directly or to other sitemaps
            ),
            Rule(
                LinkExtractor(allow=(r'/pages/sitemap.*\.xml',), allow_domains=self.allowed_domains),
                callback='parse_html_sitemap',
                follow=True
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
        # Heuristic Check 1: URL Pattern
        is_potential_product_by_url = any(regex.search(response.url) for regex in PRODUCT_PATH_REGEX)

        # Heuristic Check 2: HTML Content Analysis (if potentially product or unknown)
        is_confirmed_product_by_html = False
        if is_potential_product_by_url or not any(regex.search(response.url) for regex in LISTING_PATH_REGEX): # If URL looks like product OR not clearly a listing page
             if self.is_product_page(response):
                  is_confirmed_product_by_html = True

        # Decision: Take the item if confirmed product
        if is_confirmed_product_by_html:
             domain = urlparse(response.url).netloc.replace('www.', '')
             if domain in self.found_products:
                 if response.url not in self.found_products[domain]:
                     self.logger.info(f"Found product: {response.url}")
                     item = ProductItem()
                     item['domain'] = domain
                     item['url'] = response.url
                     self.found_products[domain].add(response.url) # Add to our tracking set
                     yield item
                 else:
                    self.logger.debug(f"Duplicate product item skipped: {response.url}")
             else:
                 self.logger.warning(f"Domain {domain} from URL {response.url} not in tracked domains.")

        if not is_confirmed_product_by_html:
            self.logger.debug(f"Attempting to extract product links from listing page: {response.url}")
            
            # Grab all <a href="..."> links on the page
            href_links = response.css('a::attr(href)').getall()
            for href in href_links:
                full_url = response.urljoin(href)  # Normalize relative → absolute

                # Check against known product patterns
                if any(regex.search(full_url) for regex in PRODUCT_PATH_REGEX):
                    domain = urlparse(full_url).netloc.replace('www.', '')
                    
                    if domain in self.found_products and full_url not in self.found_products[domain]:
                        self.logger.info(f"Found product link on listing page: {full_url}")
                        yield scrapy.Request(full_url, callback=self.parse_page)
    


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
        # Use Scrapy's Sitemap class for proper namespace handling
        sitemap = scrapy.utils.sitemap.Sitemap(response.body)
        for entry in sitemap:
            url = entry['loc']
            # Optional: Check if URL matches product patterns before yielding
            # if any(regex.search(url) for regex in PRODUCT_PATH_REGEX):
            # Use parse_page which contains the product check logic
            yield scrapy.Request(url, callback=self.parse_page)
            # else: # Or just request all URLs from sitemap
            # yield scrapy.Request(url, callback=self.parse_page)