# Documentation

## What ecomCrawler does: Gives you clickable links from Ecommerce websites like Westside and Virgio in JSON format separated by domains

## Decisions

1. Choosing the stack:

   - We will be using Python cause it has a lot of libraries for web crawling
   - We will use Scrapy framework as it is specifically designed for web crawling. It also handles duplicated by default

2. How to Identify URLs:

   - We will be using Regex to match the URLs we find to find the product URLs from there
   - We will be denying following some URLs such as Profile page, Cart page etc as it will unnecessarily lead us to URLs which are not needed

3. Settings.py

   - Running the Crawler with different conmbination of setting will allow us to check how many concurrent requests we can work with and we will also be configuring it to obey robots.txt
   - Running the crawler few times and checking the logs to find the URL types that don't give us valid results to include them in the deny url list
   - add -s LOG_FILE=log.txt -s LOG_LEVEL=INFO at the end of run command to check the logs from the log file and find denyable URL patterns
   - The crawler is working in virgio but having issues with westside as the links in westside are js-rendered

4. Addition of Playwright

   - Added playwright to find links that are js-rendered
   - Had some trouble maintaining the backward compatibility after the addition of Playwright
   - Decided to use Playwright only for websites that have JS-rendered product links
   - Need to find the pattern on when to use PlayWright and when to use Pure Scrapy as Scrapy is much faster
   - Use Regex to handle the collection pages

5. Issues based on websites
   - VIRGIO worked pretty fine with jsut scrapy as the links were embedded in HTML itself
   - Westside links are JS-rendered which I figured after a lot of effort
   - Started setting up Playwright for JS-rendered links
   - Now as playwright takes more time and resources had to shift to hybrid model such that collection links will be crawled using Playwright as they are JS-rendered but once product links are foudn they are crawled using scrapy
   - Tatacliq has been challenging and still isn't working as they are not following standards in their pages.
   - Got blocked from nykaafashion and wasn't able to crawl even with ROBOTSTXT_OBEY = False
   - Latest code has't been pushed as in efforts of making it work with TataCliq the code quality reduced significantly.

## How to run

1. Install all the packages using pip install -r requirements.txt
2. Run command => scrapy crawl ecom_product_spider -a domains="virgio.com,westside.com" -s LOG_FILE=log.txt -s LOG_LEVEL=INFO from root directory
