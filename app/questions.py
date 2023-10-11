import inquirer
from termcolor import colored
from inquirer.themes import load_theme_from_dict as loadth

from .config import *

def get_action():
    theme = {
        "Question": {
            "brackets_color": "bright_yellow"
        },
        "List": {
            "selection_color": "bright_blue"
        }
    }

    question = [
        inquirer.List(
            "action",
            message=colored("请选择操作", 'light_yellow'),
            choices=["获取所有钱包中所有代币的余额", "获取特定代币的余额", "帮助", "退出"],
        )
    ]
    action = inquirer.prompt(question, theme=loadth(theme))['action']
    return action

def select_chains(chains):
    theme = {
        "Question": {
            "brackets_color": "bright_yellow"
        },
        "List": {
            "selection_color": "bright_blue"
        }
    }

    question = [
        inquirer.Checkbox(
            "chains",
            message=colored("请选择要获取余额的网络（使用箭头键左右选择答案）", 'light_yellow'),
            choices=["全部网络", *chains],
        )
    ]
    selected_chains = inquirer.prompt(question, theme=loadth(theme))['chains']
    if ('全部网络' in selected_chains):
        return chains
    return selected_chains

def get_ticker():
    theme = {
        "Question": {
            "brackets_color": "bright_yellow"
        },
        "List": {
            "selection_color": "bright_blue"
        }
    }

    question = [
        inquirer.Text("ticker", message=colored("请输入代币名称（Ticker）", 'light_yellow'))
    ]
    ticker = inquirer.prompt(question, theme=loadth(theme))['ticker'].upper()
    return ticker

def get_minimal_amount_in_usd():
    while True:
        theme = {
            "Question": {
                "brackets_color": "bright_yellow"
            },
            "List": {
                "selection_color": "bright_blue"
            }
        }

        question = [
                inquirer.Text("min_amount", message=colored("请输入最小显示余额的金额（以$为单位）", 'light_yellow'), default="0.01")
        ]
        try:
            min_amount = float(inquirer.prompt(question, theme=loadth(theme))['min_amount'].strip())
            break
        except:
            logger.error('错误！无效输入')
    if (min_amount) == 0:
        min_amount = -1
    return min_amount

def get_num_of_threads():
    while True:
        theme = {
            "Question": {
                "brackets_color": "bright_yellow"
            },
            "List": {
                "selection_color": "bright_blue"
            }
        }

        question = [
                inquirer.Text("num_of_threads", message=colored("请输入工作线程数", 'light_yellow'), default="3")
        ]
        try:
            num_of_threads = int(inquirer.prompt(question, theme=loadth(theme))['num_of_threads'].strip())
            break
        except:
            logger.error('错误！无效输入')
    if (num_of_threads) == 0:
        num_of_threads = 3
    return num_of_threads
