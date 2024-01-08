# MOEX Trends Catcher
## Preface
This app uses [/iss/engines/[engine_name]/markets/[market_name]/securities/[security_name]/candles](https://iss.moex.com/iss/reference/155)
endpoint of MOEX Informational Statistical Server to get OHLCV (open, high, low, close, volume) data for different securities. You need to know **engine**, **market** and **security** params to use this app.

All possible *engine* and *market* MOEX ISS names - [/iss/index](https://iss.moex.com/iss/index)

You can find **engine** and **market** parameters for your **security** using this request
[/iss/securities?q=..](https://iss.moex.com/iss/securities?q=)<br>
E.g., the value of the column *group* is *stock_shares* for *q=GAZP*. Use *stock* as engine and *shares* as market.
Other parameters of this end point - [/iss/reference/5](https://iss.moex.com/iss/reference/5).

You can find more information about MOEX Informational Statistical Server and its RESTful API using this link - [https://www.moex.com/a2193](https://www.moex.com/a2193).


## The app features
Implemented navigation menu tabs:
1. **Home** (for all users)<br>
Information about app, login and registration form links.
2. **Account** (for authenticated users)<br>
Profile edit and password change links to corresponding forms.
3. **Settings of securities** (for authenticated users)<br>
CRUD operations for settings of favourite user's securities.<br>
Every setting include GET request params (engine, market, security, duration of time series, data interval) and *maximum refresh rate* of OHLCV data.<br>
User can drag settings to reorder them.<br>
GET requests to MOEX ISS are executed asynchronously for securities without saved data or which data in database are too old. Whether data is too old is determined by *maximum refresh rate* param of setting. All GET requests are executed only when user opens *Candles* tab.<br>
If GET request is successful, setting border color is green else red. While no requests were sent, setting border color is blue.
There's one limitation in this version of the app - you can fetch a maximum of only 500 last time intervals for a single security. But it's enough to catch current trend.
4. **Candles** (for authenticated users)<br>
Charts for securities with tunable sizes. An order of securities in charts is determined by order of security settings in *Settings of securities* tab.
5. **Returns** (for authenticated users)<br>
5.1. **The form for creation of background celery task** to find best long and short deal returns on historical data for all securities loaded by all users.<br>
Parameters of task are duration of time series, different types of fees in percentages, risk free return (a percentage per annum), what type of return to use for results sorting (return per deal in percentages or return recalculated as a percentage per annum), what data to use from every interval (Open-Close or High-Low).<br>
When High-Low is choosed, High-Low data are extracted for long deal calculations and *Low-High* data are extracted for short deals because we don't know what value was in the interval the first, High or Low, therefore the worst case is considered.<br>
5.2. **Results of finished task** in 2 tables in sorted by return order.<br>
All OHLC data for calculations are loaded only from database, filtered based on *duration* param of task form and ordered by last datetime of security data in descending order. No more than one table row is issued for each security.
Risk-adjusted performance measures are calculated for every security in the results table.


## Tech stack
* Python 3.10
* Django 4.2
* PostgreSQL - the main relational database
* asyncio, aiohttp - for async requests to MOEX ISS
* Celery, Redis, RabbitMQ - for background celery task
* Docker - for postgres, redis, rabbitmq services
* crispy_forms, crispy-bootstrap5 - for forms in templates
* bootstrap5, echarts, jquery, datatables - for UI


## Demo video
https://github.com/AtLeisureTime/MOEX_Trends_Catcher/assets/16018457/ac8502d4-e3cc-4bf1-bc3b-016f26faf3d5

## Run

### Requirements
* Linux
* Python 3.10+
* Docker

### Local run:

* Terminal 1
```
git clone https://github.com/AtLeisureTime/MOEX_Trends_Catcher.git
cd MOEX_Trends_Catcher/

python3 -m venv my_env
source my_env/bin/activate
pip install -r requirements.txt

set -a
source .live.env
set +a
export DJANGO_SETTINGS_MODULE=app.settings.local

docker compose -f docker-compose.local.yaml up --build
..
docker compose -f docker-compose.local.yaml down -v
deactivate
```
* Terminal 2
```
source my_env/bin/activate
set -a
source .live.env
set +a
export DJANGO_SETTINGS_MODULE=app.settings.local

python app/manage.py makemigrations
python app/manage.py migrate
python app/manage.py createsuperuser
python app/manage.py runserver
..
deactivate
```
* Terminal 3
```
source my_env/bin/activate
set -a
source .live.env
set +a
export DJANGO_SETTINGS_MODULE=app.settings.local
cd app/
celery -A app worker -l info
..
deactivate
```

### Demo data
Application demo data (security settings) are in **test_data/**. Run this line locally to load test data to the database:
```
python app/manage.py loaddata test_data/app_data.json
```
