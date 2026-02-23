from massive import RESTClient
from datetime import datetime
import time

secret_key = 'V_l8Vd7MHKIrpa3Oznh09tfShEMDK1eB'
client = RESTClient(api_key=secret_key)
tickers = []




rsi = client.get_rsi(
    ticker="X:HYPEUSD",
	timespan="minute",
	window="14",
	series_type="close",
	order="desc",
	limit="100"
)

for i in rsi.values:
    print('--------')
    print(i.value)
    print(datetime.fromtimestamp(i.timestamp/1000).strftime('%Y-%m-%d %H:%M:%S'))
