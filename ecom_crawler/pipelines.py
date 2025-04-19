import json
from itemadapter import ItemAdapter
from collections import defaultdict

class GroupedOutputPipeline:
    def open_spider(self, spider):
        # Use defaultdict to easily collect URLs per domain
        self.products_by_domain = defaultdict(set) # Use set for automatic uniqueness

    def close_spider(self, spider):
        # Called when the spider finishes
        output_data = {}
        for domain, urls in self.products_by_domain.items():
            # Convert set to sorted list for consistent output
            output_data[domain] = sorted(list(urls))

        # Define output filename (could be passed via settings or spider args)
        output_filename = 'grouped_products.json'
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            spider.logger.info(f"Successfully saved grouped product URLs to {output_filename}")
        except IOError as e:
            spider.logger.error(f"Error writing grouped output file: {e}")


    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        domain = adapter.get('domain')
        url = adapter.get('url')

        if domain and url:
            # Add URL to the set for the corresponding domain
            self.products_by_domain[domain].add(url)
        else:
            spider.logger.warning(f"Item missing domain or URL: {item}")

        # We don't return the item because this pipeline handles the final output
        return item # Return item if you want other pipelines (like default FeedExporter) to see it too
                   # If ONLY using this pipeline for output, dropping is fine. Let's return it
                   # to allow flexibility (e.g., using FEEDS for a flat CSV alongside this grouped JSON).