from WLO.src.MessageCreatorAbs import *
import logging
import json
from datetime import datetime
import os
from WLO.src.Utils.Utils import *

DRIVER_PREFIX = "MessageCreator-Driver-WebScraping: "
#SCRAP_WORKER_FULL_PATH = os.path.dirname(os.path.abspath(__file__))

class MessageCreator(MessageCreatorAbstract):

    def __init__(self, params):
        super().__init__(params)
        #self.isItRoot = params['isRoot']


        self.urls_file_path = params['urls']
        self.is_inline_urls = params['isUrlsInline'] if 'isUrlsInline' in params else False
        self.scraping_flow = params['scarpFlowYAml']

    def create_messages(self, queue):
        dateTimeObj = datetime.now()
        urls = []

        if self.is_inline_urls:
            urls = self.urls_file_path.split(',')
            for url in urls:
                work = dict(
                    params=dict(worker_driver='WebSitesScrapingWorker'),
                    payload=dict(scrap_flow=self.scraping_flow, url_to_scrap=url)
                )
                logging.debug(f"{DRIVER_PREFIX} Going to send the work - {work}")
                queue.put(work)

        else:
            with open(self.urls_file_path, 'r') as file:
                content = json.load(file)

            for title, urls in content.items():
                for url in urls:
                    work = dict(
                        params=dict(worker_driver='WebSitesScrapingWorker',title=title),
                        payload=dict(scrap_flow=self.scraping_flow, url_to_scrap=url)
                    )
                    logging.debug(f"{DRIVER_PREFIX} Going to send the work - {work}")
                    queue.put(work)




def init(params):
    return MessageCreator(params)

def test():
    logging.basicConfig(format='[%(asctime)s -%(levelname)s] (%(processName)-10s) %(message)s')

    logging.getLogger().setLevel('DEBUG')
    works_execution_params = dict()
    if "EXECUTION_PARAMS" in os.environ:
        works_execution_params = json.loads(os.environ["EXECUTION_PARAMS"])
    creator = MessageCreator(works_execution_params)
    creator.create_messages(get_syncro_queue())


