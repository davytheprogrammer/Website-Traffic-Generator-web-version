import app
import os
import sys
import json
import random
import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

import argparse
import threading
from app import generate_traffic
THREADS         = []
PROXIES         = []

# Argument handling
parser = argparse.ArgumentParser(description='Generate traffic on a domain')
parser.add_argument('-d', '--domain', required=True, type=str, help="The domain to generate traffic on")
parser.add_argument('-s', '--secure', required=False, dest='secure', action='store_true', help="Use a secure connection")
parser.add_argument('-f', '--forever', required=False, dest="forever", action="store_true", help='Run forever')
parser.add_argument('-t', '--threads', required=False, type=int, default=5, help='Number of threads to use')
parser.add_argument('-to', '--timeout', required=False, type=int, default=30, help='Request timeout  in seconds')
parser.add_argument('-mo', '--max-offset', required=False, type=int, default=3, help='Max timeout between link clicks')
parser.add_argument('-mac', '--max-clicks', required=False, type=int, default=5, help='Max number of link clicks per thread.')
parser.add_argument('-mic', '--min-clicks', required=False, type=int, default=1, help='Max number of link clicks per thread.')
parser.add_argument('-pf', '--proxy_file', required=False, type=str, default="", help='Path to a HTTP proxy list file. One proxy host:port per line')
parser.set_defaults(secure=False)
parser.set_defaults(forever=False)

args = parser.parse_args()

# Check argumens for their validity
if args.proxy_file != "" and not os.path.isfile(args.proxy_file):
    print( "File {} does not exist.".format(args.proxy_file))
    sys.exit(1)
elif args.proxy_file != "" and os.path.isfile(args.proxy_file):
    # Read proxies from the proxy file. Only http proxies are supported for now.
    PROXIES = list(map(lambda x: x.strip(), open(args.proxy_file, "r").readlines()))

if args.threads < 1:
    print ("Minimum of 1 thread required.")
    sys.exit(1)

if args.timeout < 0:
    print( "Timeout must be positive.")
    sys.exit(1)

if args.max_offset < 0:
    print ("Max offset must be positive")
    sys.exit(1)

if args.max_clicks < 0:
    print ("Max clicks must be positive")
    sys.exit(1)

if args.min_clicks < 0:
    print ("Min clicks must be positive")
    sys.exit(1)


# main traffic generating method, which is executed by each thread.
def generate_traffic(args):
    # Run forever if --forever is set. Check is done at the loop's end, so that we run this at least once.
    while True:
        settings = ['--ignore-ssl-errors=true', f'--proxy-server={ip}']
        ip = "random.choice(PROXIES)"
        # We might need to use a proxy. Choose one randomly.
        if len(PROXIES) != 0:
            ip = random.choice(PROXIES)
            settings += ["--proxy-server={}".format(ip)]

        CHROMEDRIVER_PATH = "C:/Users/user/Downloads/python-trafficgenerator-master/python-trafficgenerator-master/chromedriver"
        service = webdriver.chrome.service.Service(CHROMEDRIVER_PATH)

        # Create ChromeOptions and set the desired settings
        # Create ChromeOptions and set the desired settings
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")  # Run Chrome in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")

        # Create a ChromeDriver instance
        driver = webdriver.Chrome()
        Service = service
        #Options = chrome_options

        # Set page load timeout and window size
        driver.set_page_load_timeout(args.timeout)
        driver.set_window_size(1024, 768)

        # Our initial URL is just the domain.
        url = "{}{}".format("https://" if args.secure else "http://", args.domain)
        try:
            driver.get(url)

            # Rest of the code within the while loop

            # We want to simulate [N_min, N_max] random clicks on a randomly chosen link on a page.
            for i in range(random.randint(args.min_clicks, args.max_clicks + 1)):
                try:
                    # Get a list of all links on that page.
                    links = driver.find_elements(By.XPATH, "//a[@href]")
                    # Only click on links that are on the same domain.
                    links = list(filter(lambda x: args.domain in x.get_attribute("href"), links))

                    # Wait before our next click. We don't want to be too fast.
                    time.sleep(random.randint(0, args.max_offset * 1000) / 1000)
                    print("[{}][{}] Found {} links".format(time.strftime("%H:%M:%S", time.gmtime()), ip, len(links)))
                    # If there are no links, we go back.
                    if len(links) == 0:
                        print("[{}][{}] Visiting now: {}".format(time.strftime("%H:%M:%S", time.gmtime()), ip, "previous page"))
                        driver.back()
                        continue
                    # Ok, there is a new link to click. Visit it.
                    next_link = random.choice(links)
                    print("[{}][{}] Visiting now: {}".format(time.strftime("%H:%M:%S", time.gmtime()), ip, next_link.get_attribute("href")))
                    driver.get(next_link.get_attribute("href"))
                except:
                    continue
        except TimeoutException:
            continue
        except:
            pass
        finally:
            driver.quit()
            # Do we want to do this forever?
            if not args.forever:
                break

        # Wait before generating traffic again.
        time.sleep(random.randint(args.max_offset, args.max_offset * 2))


generate_traffic(args)
# Start N threads. Wait between thread starts.
for i in range(args.threads):
    t = threading.Thread(target=generate_traffic, args=(args,))
    THREADS.append(t)
    t.start()
    time.sleep(random.randint(args.timeout // 11, args.timeout))

# Wait for all threads to finish.
for t in THREADS:
    t.join()



