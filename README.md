TrafficGenerator
======
This tool can be used to generate real (fake) traffic on a specific website (domain). It uses the headless browser phantomjs, so that all content will be rendered similar to a real browser, making it hardly to distinguish. 
HTTP proxy lists and random user agents are also supported. 

After visiting a page the tool will randomly select one link from the page and click on it. Only links from the same domain are visisted.

## Usage 
The usage should be quite simple. 

Download and prepare a HTTP proxy list:

```
$> curl  http://txt.proxyspy.net/proxy.txt -o- | grep '+ $'| awk -F' ' '{print $1}' | sort -R > proxies.txt
```run the app.py
download the latest chromedriver

## License

See LICENCE.md
