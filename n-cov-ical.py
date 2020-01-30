from icalendar import Calendar, Event
import requests
import logging
import json
from datetime import datetime, timedelta
from os import path
import vtimezone


class FetchException(Exception):
    pass


# 获取最新的数据
FIELDS = dict(
    updated_at='updateTime',
    confirmed='confirmedCount',
    suspected='suspectedCount',
    cured='curedCount',
    dead='deadCount',
)

STORAGE_PATH = path.join(path.dirname(path.realpath(__file__)), 'data', 'save-file')
OUTPUT_PATH = path.join(path.dirname(path.realpath(__file__)), 'public', '2019-n-Cov-ical.ics')


def fetch_latest_data():
    try:
        response = requests.get(
            url="https://lab.isaaclin.cn/nCoV/api/overall",
        )
        if response.status_code > 299:
            logging.error('fetch data error with wrong status code = {status_code}'.format(
                status_code=response.status_code
            ))
            raise FetchException('status code error')
    except requests.exceptions.RequestException as err:
        logging.error('request error')
        raise err
    payload = ''
    try:
        payload = json.loads(response.content.decode('utf-8'))
    except json.JSONDecodeError as err:
        logging.error('api returns invalid json')
        raise err

    if 'success' not in payload or not payload['success']:
        logging.error('api returns error')
        raise FetchException('api not returns success')
    if 'results' not in payload or len(payload['results']) == 0:
        logging.error('api\'s return not contains data')
        raise FetchException('api returns empty results')

    latest_data = payload['results'][0]
    for field in FIELDS.values():
        if field not in latest_data:
            error_message = 'filed `{field}` not found'.format(
                field=field
            )
            logging.error(error_message)
            raise FetchException(error_message)
    return parse_data(latest_data)


def parse_data(data):
    # 初始化返回值
    ret = dict()
    for key in FIELDS:
        value = data[FIELDS[key]]
        if key == 'updated_at':
            continue
        ret[key] = value
    time = datetime.utcfromtimestamp(int(data[FIELDS['updated_at']] / 1e3))
    date_string = time.strftime('%Y-%m-%d')
    updated_at = time.strftime('%Y-%m-%d %H:%M:%S')
    uid = 'ical-2019-nCov-{date}'.format(
        date=date_string
    )
    ret['uid'] = uid
    ret['updated_at'] = updated_at
    ret['updated_at_unix_timestamp'] = int(data[FIELDS['updated_at']] / 1e3)
    return ret


def load_storage():
    try:
        with open(STORAGE_PATH, 'r') as f:
            content = f.read()
    except FileNotFoundError as err:
        logging.warning('storage file not found')
        return []

    try:
        ret = json.loads(content, 'utf-8')
    except json.JSONDecodeError as err:
        logging.error('invalid storage format')
        raise err
    return sorted(ret, key=lambda data: data['updated_at_unix_timestamp'])


def new_ical():
    calendar = Calendar()
    calendar['dtstart'] = '20200120T080000'
    calendar['summary'] = '全国新型肺炎疫情实时日历'
    calendar.add('prodid', 'n-Cov-ical')
    calendar.add('x-wr-calname', '全国新型肺炎疫情实时日历')
    vtz = vtimezone.generate_vtimezone('Asia/Shanghai')
    calendar.add_component(vtz)
    return calendar


def new_event(record):
    event = Event()
    event.add('summary', f'新型肺炎日报 确诊:{record["confirmed"]}/疑似:{record["suspected"]}'
                         f'/死亡:{record["dead"]}/治愈:{record["cured"]}')
    event_time = datetime.utcfromtimestamp(record['updated_at_unix_timestamp'])
    event_today = event_time.date()
    event_tomorrow = (event_time + timedelta(days=1)).date()
    event.add('dtstart', event_today)
    event.add('dtend', event_tomorrow)
    event.add('uid', record['uid'])
    event.add('dtstamp', event_time)
    event.add('last-modified', event_time)
    return event


def make_ical():
    ical = new_ical()
    record = fetch_latest_data()
    ical.add_component(new_event(record))
    return ical


def main():
    cal_str = make_ical().to_ical()
    with open(OUTPUT_PATH, 'wb+') as f:
        f.write(cal_str)
        print(cal_str.decode('utf-8').replace('\\r\\n', '\n'))


if __name__ == '__main__':
    main()
