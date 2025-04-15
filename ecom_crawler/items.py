# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class EcomCrawlerItem(scrapy.Item):
    # defining the fields for our item here 
    domain = scrapy.Field()
    url = scrapy.Field()
    
