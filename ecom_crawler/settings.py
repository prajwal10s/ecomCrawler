
BOT_NAME = "ecom_crawler"

SPIDER_MODULES = ["ecom_crawler.spiders"]
NEWSPIDER_MODULE = "ecom_crawler.spiders"



# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = 'ecom_crawler (+http://justCrawlingForFun.com)' 

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 16 # Depending on the machine, can be adjusted
CONCURRENT_REQUESTS_PER_DOMAIN = 4 # domains should't be overburdened
DOWNLOAD_DELAY = 0.5 # Start with a delay, let AutoThrottle adjust if enabled
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0 # Aim for average 4 requests/domain concurrently
# AUTOTHROTTLE_DEBUG = True # Enable to see throttling decisions


# --- Crawling Strategy ---
DEPTH_LIMIT = 0 # 0 means no limit, you can set > 0 to limit crawl depth if needed(in case its taking too long due to number of products)
#DEPTH_PRIORITY = 1 # Try=> BFS (Breadth-First Search)

ITEM_PIPELINES = {
   'ecom_crawler.pipelines.GroupedOutputPipeline': 300,
}

#Playwright settings

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}

# Optional for performance:
DOWNLOAD_HANDLERS_BASE = {
    'https': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
    'http': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
}


LOG_LEVEL = 'WARNING'