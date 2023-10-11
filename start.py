import threading
import openpyxl

from queue import Queue
from time import time

from art import text2art
from alive_progress import alive_bar

from app.excel import *
from app.questions import *
from app.config import *
from app.utils import *


def chain_balance(node_process, session, address, chain, ticker, min_amount):
    coins = []

    payload = {
        'user_addr': address,
        'chain': chain
    }
    edit_session_headers(node_process, session, payload, 'GET', '/token/balance_list')

    resp = send_request(
        node_process,
        session=session,
        method='GET',
        url=f'https://api.debank.com/token/balance_list?user_addr={address}&chain={chain}',
    )

    for coin in resp.json()['data']:
        if (ticker == None or coin['optimized_symbol'] == ticker):
            coin_in_usd = '?' if (coin["price"] is None) else coin["amount"] * coin["price"]
            if (type(coin_in_usd) is str or (type(coin_in_usd) is float and coin_in_usd > min_amount)):
                coins.append({
                    'amount': coin['amount'],
                    'name': coin['name'],
                    'ticker': coin['optimized_symbol'],
                    'price': coin['price'],
                    'logo_url': coin['logo_url']
                })

    return coins


def show_help():
    print(
        '--------------------- 帮助 ---------------------\n> 什么是最小美元代币金额？\n> 如果代币的美元金额低于指定的最小金额，则不会在表格中显示\n\n> 如何选择所有网络？\n> 在选择网络时，请选择“所有网络”选项（右箭头）然后按Enter键\n\n> 什么是工作线程数？\n> 这是同时获取钱包信息的“工作进程”数量。工作线程数越多，被Cloudflare阻止的机会就越高。建议使用3个线程\n\n> 进度条不动，怎么办？\n> 减少工作线程数 / 检查网络连接\n\n> "网络" 和 "总计" 列有什么区别？\n> 第一列是所选网络和池中的所有代币的美元总值，第二列是所有网络的美元总值\n\n> 为什么获取用于钱包的网络列表需要如此长的时间？\n> 因为Cloudflare会对这个请求进行严格的检查，所以请求必须在单线程模式下执行\n\n> 有其他问题吗？\n> 在我们的聊天室中与我们联系 https://t.me/cryptogovnozavod_chat\n--------------------- 帮助 ---------------------\n')


def get_used_chains(node_process, session, address):
    payload = {
        'id': address,
    }
    edit_session_headers(node_process, session, payload, 'GET', '/user/used_chains')

    resp = send_request(
        node_process,
        session=session,
        method='GET',
        url=f'https://api.debank.com/user/used_chains?id={address}',
    )

    chains = resp.json()['data']['chains']

    return chains


def get_chains(node_process, session, wallets):
    chains = set()

    with alive_bar(len(wallets)) as bar:
        for wallet in wallets:
            chains = chains.union(get_used_chains(node_process, session, wallet))
            bar()

    print()
    return chains


def get_wallet_balance(node_process, session, address):
    payload = {
        'user_addr': address,
    }
    edit_session_headers(node_process, session, payload, 'GET', '/asset/net_curve_24h')

    resp = send_request(
        node_process,
        session=session,
        method='GET',
        url=f'https://api.debank.com/asset/net_curve_24h?user_addr={address}',
    )

    usd_value = resp.json()['data']['usd_value_list'][-1][1]

    return usd_value


def get_pools(node_process, session, wallets):
    def get_pool(session, address):
        pools = {}
        payload = {
            'user_addr': address,
        }
        edit_session_headers(node_process, session, payload, 'GET', '/portfolio/project_list')

        resp = send_request(
            node_process,
            session=session,
            method='GET',
            url=f'https://api.debank.com/portfolio/project_list?user_addr={address}',
        )

        for pool in resp.json()['data']:
            pools[f"{pool['name']} ({pool['chain']})"] = []
            for item in pool['portfolio_item_list']:
                for coin in item['asset_token_list']:
                    pools[f"{pool['name']} ({pool['chain']})"].append({
                        'amount': coin['amount'],
                        'name': coin['name'],
                        'ticker': coin['optimized_symbol'],
                        'price': coin['price'],
                        'logo_url': coin['logo_url']
                    })

        return pools

    all_pools = {}

    with alive_bar(len(wallets)) as bar:
        for wallet in wallets:
            pools = get_pool(session, wallet)
            for pool in pools:
                if (pool not in all_pools):
                    all_pools[pool] = {}
                all_pools[pool][wallet] = pools[pool]
            bar()

    for pool in all_pools:
        for wallet in wallets:
            if (wallet not in all_pools[pool]):
                all_pools[pool][wallet] = []
    print()

    return all_pools


def worker(queue_tasks, queue_results):
    session, node_process = setup_session()

    while True:
        task = queue_tasks.get()
        if (task[0] == 'chain_balance'):
            balance = chain_balance(node_process, session, task[1], task[2], task[3], task[4])
            queue_results.put((task[2], task[1], balance))
        elif (task[0] == 'get_wallet_balance'):
            balance = get_wallet_balance(node_process, session, task[1])
            queue_results.put((task[1], balance))
        elif (task[0] == 'done'):
            queue_tasks.put(('done',))
            break


def get_balances(wallets, ticker=None):
    session, node_process = setup_session()

    logger.info('获取用于钱包的网络列表...')
    chains = list(get_chains(node_process, session, wallets))
    logger.info('获取池和钱包余额信息...')
    pools = get_pools(node_process, session, wallets)
    logger.success(f'完成！总共的网络和池数量：{len(chains) + len(pools)}\n')

    min_amount = get_minimal_amount_in_usd()
    num_of_threads = get_num_of_threads()
    selected_chains = select_chains(chains + [pool for pool in pools])

    coins = {chain: dict() for chain in selected_chains}
    coins.update(pools)
    pools_names = [pool for pool in pools]

    queue_tasks = Queue()
    queue_results = Queue()

    threads = []
    for _ in range(num_of_threads):
        th = threading.Thread(target=worker, args=(queue_tasks, queue_results))
        threads.append(th)
        th.start()

    start_time = time()
    for chain_id, chain in enumerate(selected_chains):
        if (chain not in pools_names):
            logger.info(
                f'[{chain_id + 1}/{len(selected_chains) - len(set(selected_chains) & set(pools_names))}] 获取 {chain.upper()} 网络的余额...')

            for wallet in wallets:
                queue_tasks.put(('chain_balance', wallet, chain, ticker, min_amount))

            with alive_bar(len(wallets)) as bar:
                for wallet in wallets:
                    result = queue_results.get()
                    coins[result[0]][result[1]] = result[2]
                    bar()

    print()
    logger.info('获取每个钱包的所有网络余额信息')
    for wallet in wallets:
        queue_tasks.put(('get_wallet_balance', wallet))

    balances = {}
    with alive_bar(len(wallets)) as bar:
        for wallet in wallets:
            result = queue_results.get()
            balances[result[0]] = result[1]
            bar()

    queue_tasks.put(('done',))
    for th in threads:
        th.join()

    if (ticker is None):
        save_full_to_excel(wallets, selected_chains, coins, balances)
    else:
        save_selected_to_excel(wallets, selected_chains, coins, balances, ticker)

    print()
    logger.success(f'完成！表格已保存到 {file_excel}')
    logger.info(f'花费时间: {round((time() - start_time) / 60, 1)} 分钟\n')


def main():
    art = text2art(text="DEBANK   CHECKER", font="standart")
    print(colored(art, 'light_blue'))
    print(colored('作者: t.me/cryptogovnozavod\n', 'light_cyan'))

    with open(file_wallets, 'r') as file:
        wallets = [row.strip().lower() for row in file]

    logger.success(f'成功加载 {len(wallets)} 个地址\n')

    while True:
        action = get_action()

        match action:
            case '获取所有钱包中所有代币的余额':
                get_balances(wallets)
            case '获取特定代币的余额':
                ticker = get_ticker()
                get_balances(wallets, ticker)
            case '帮助':
                show_help()
            case '退出':
                exit()
            case _:
                pass


if (__name__ == '__main__'):
    main()
