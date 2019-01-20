import json
import time
import datetime as dt
from websocket import create_connection

basket = 'BTC_USDT'
exchange = 'binance'
path = 'ws://188.166.122.193:8080/prices/ws'
precision = 100000000
n = 7
ema_0 = 3700.22
U_factor, U_addend = 2.083, 3574.83
D_factor, D_addend = -2.214, 3600.39
simulation_time = 3 * 60 * 60
dump_time = 5 * 60


def u():
    return U_factor * curhour() + U_addend


def d():
    return D_factor * curhour() + D_addend


def p(assks, bidss):
    return (assks[0][0] + bidss[0][0]) / 2


def curhour():
    return dt.datetime.today().hour


def emacalc(emaa, pcur):
    return (pcur - emaa) * (2 / (n + 1)) + emaa


def updateorders(order, data, increase):
    rate = (float(data['rate']) / precision)
    amount = (float(data['amount']) / precision)
    if data['action'] == 'remove':
        for pair in order:
            if pair[0] == rate:
                order.remove(pair)
    if data['action'] == 'insert':
        for pair in order:
            if pair[0] == rate:
                pair = (rate, amount)
            if increase:
                if pair[0] < rate:
                    order.insert(order.index(pair), (rate, amount))
                    break
            else:
                if pair[0] > rate:
                    order.insert(order.index(pair), (rate, amount))
                    break
    return order


def get_updates(ws, asks, bids, timer, dump_timer, ema):
    updates, actions = [], []
    start_time = time.time()
    open_position = False
    dump_count = 1
    lastaction = ''
    while True:
        running_time = time.time() - start_time
        p_cur = p(asks, bids)
        resultjs = json.loads(ws.recv())
        if resultjs[0][0] == 'price_inc':
            if (resultjs[0][1]['pair'] == basket) & (resultjs[0][1]['exchange'] == exchange):
                for results in resultjs[0][1]['data']:
                    if results['type'] == 'bid':
                        asks = updateorders(asks, results, True)
                    else:
                        bids = updateorders(bids, results, False)
                    p_prev = p_cur
                    p_cur = p(asks, bids)
                    ema = emacalc(ema, p_cur)
                    updates.append([{'ts': time.time(), 'cur_ema': ema, 'cur_p': p_cur}])
                    if p_cur > p_prev:
                        trenddir = 'rise'
                    else:
                        trenddir = 'fall'
                    if not open_position:
                        if ema > u():
                            if p_cur > p_prev:
                                lastaction = 'close_buy'
                                actions.append({'ts': time.time(), 'action': 'buy', 'rate': p_cur, 'cur_ema': ema,
                                                'trend_dir': trenddir})
                            else:
                                lastaction = 'close_sell'
                                actions.append({'ts': time.time(), 'action': 'sell', 'rate': p_cur, 'cur_ema': ema,
                                                'trend_dir': trenddir})
                            open_position = True
                    else:
                        if ema < d():
                            actions.append({'ts': time.time(), 'action': lastaction, 'rate': p_cur, 'cur_ema': ema,
                                            'trend_dir': trenddir})
                            open_position = False
        if running_time > dump_timer * dump_count:
            dump_count = dump_count + 1
            with open('res.log', 'a') as outfile:
                if updates:
                    json.dump(updates, outfile)
                if actions:
                    json.dump(actions, outfile)
            updates, actions = [], []

        if running_time > timer:
            for i in range(len(asks)):
                asks[i] = (int(asks[i][0] * precision), int(asks[i][1] * precision))
            for i in range(len(bids)):
                bids[i] = (int(bids[i][0] * precision), int(bids[i][1] * precision))
            if open_position:
                actions.append({'ts': time.time(), 'action': lastaction, 'rate': p_cur, 'cur_ema': ema,
                                'trend_dir': trenddir})
            with open('data.log', 'a') as outfile:
                json.dump(
                    [['price', {'exchange': exchange, 'pair': basket, 'ts': time.time(), 'asks': asks, 'bids': bids}]],
                    outfile)
            with open('res.log', 'a') as outfile:
                if updates:
                    json.dump(updates, outfile)
                if actions:
                    json.dump(actions, outfile)
            print('time has passed')
            return


def get_data(timer, dump_timer, ema):
    ws = create_connection(path)
    try:
        resultjs = json.loads(ws.recv())
        asks, bids = [], []
        for results in resultjs:
            if (results[1]['pair'] == basket) & (results[1]['exchange'] == exchange):
                for pairs in results[1]['asks']:
                    asks.append((float(pairs[0]) / precision, float(pairs[1]) / precision))
                for j in results[1]['bids']:
                    bids.append((float(pairs[0]) / precision, float(pairs[1]) / precision))
        get_updates(ws, asks, bids, timer, dump_timer, ema)
    except json.decoder.JSONDecodeError:
        print('Server sent something wrong, restart the app')
    ws.close()


get_data(simulation_time, dump_time, ema_0)
