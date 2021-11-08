import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

VERSION='0.0.20'
setuptools.setup(
     name='WebGenericScraper',
     version=VERSION,
     scripts=['WebSitesScrapingWorker.py', 'ScrapingMessageCreator.py', 'WebScarpingWork'],
     author="Idan Perez",
     author_email="kimpatz@gmail.com",
     description="This is a generic web scraper fro scraping web page and execute some actions on top",
     long_description='file: README.md',
     long_description_content_type="text/markdown",
     url="https://github.com/idanp/WebGenericScraper",
     install_requires=['WLO', 'selenium', 'webdriver-manager', 'pandas', 'colorama','bs4', 'pyyaml'],
     packages=setuptools.find_packages(),
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
         "Operating System :: OS Independent",
     ],
 )