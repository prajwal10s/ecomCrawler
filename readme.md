# Documentation

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
   -
