#!/usr/bin/env python3
import os
import sys
import argparse
import requests
import json

# 向上搜尋找到最近的 .router_port 或 .cyberbrain_env
def get_router_url():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 嘗試找 .router_port
    search_dir = current_dir
    for _ in range(4):
        port_file = os.path.join(search_dir, '.router_port')
        if os.path.exists(port_file):
            try:
                with open(port_file, 'r') as f:
                    port = f.read().strip()
                return f"http://127.0.0.1:{port}"
            except:
                pass
        search_dir = os.path.dirname(search_dir)
        
    # 嘗試找 .cyberbrain_env
    search_dir = current_dir
    for _ in range(4):
        env_file = os.path.join(search_dir, 'octo_cyberbrain', '.cyberbrain_env')
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith('ROUTER_PORT='):
                            port = line.strip().split('=')[1]
                            return f"http://127.0.0.1:{port}"
            except:
                pass
        search_dir = os.path.dirname(search_dir)
        
    return "http://127.0.0.1:12210" # Default fallback

ROUTER_URL = get_router_url()

def validate_trigger_args(args):
    """前端參數防呆檢查，確保提供對應的排程參數"""
    if args.trigger == 'daily':
        if args.hour is None or args.minute is None:
            return False, "trigger 為 'daily' 時，必須指定 --hour 與 --minute"
    elif args.trigger == 'cron':
        if args.hour is None and args.minute is None and args.day_of_week is None and args.day is None:
            return False, "trigger 為 'cron' 時，至少須指定一項時間參數 (如 --hour, --minute, --day_of_week 等)"
    elif args.trigger == 'weekly':
        if args.day_of_week is None or args.hour is None or args.minute is None:
            return False, "trigger 為 'weekly' 時，必須指定 --day_of_week, --hour 與 --minute"
    elif args.trigger == 'monthly':
        if args.day is None or args.hour is None or args.minute is None:
            return False, "trigger 為 'monthly' 時，必須指定 --day, --hour 與 --minute"
    elif args.trigger == 'date':
        if not args.run_time:
            return False, "trigger 為 'date' 時，必須指定 --run_time"
    elif args.trigger == 'interval':
        if args.hours is None and args.minutes is None and args.seconds is None:
            return False, "trigger 為 'interval' 時，至少須指定 --hours, --minutes, 或 --seconds 其中之一"
    return True, ""

def register_job(args):
    valid, msg = validate_trigger_args(args)
    if not valid:
        print(f"[Error] {msg}")
        sys.exit(1)
        
    payload = {
        "id": args.id,
        "target_agent": args.target,
        "trigger": args.trigger,
        "prompt": args.prompt
    }
    
    if args.type: payload["type"] = args.type
    if args.hour is not None: payload["hour"] = args.hour
    if args.minute is not None: payload["minute"] = args.minute
    if args.second is not None: payload["second"] = args.second
    if args.day_of_week is not None: payload["day_of_week"] = args.day_of_week
    if args.day is not None: payload["day"] = args.day
    if args.hours is not None: payload["hours"] = args.hours
    if args.minutes is not None: payload["minutes"] = args.minutes
    if args.seconds is not None: payload["seconds"] = args.seconds
    if args.run_time: payload["run_time"] = args.run_time

    try:
        response = requests.post(f"{ROUTER_URL}/awake/jobs/register", json=payload, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success":
                print(f"[Success] 任務已註冊: {args.id}")
            else:
                print(f"[Error] 註冊失敗: {res_data.get('message', '未知錯誤')}")
        else:
            print(f"[Error] API 回應錯誤: HTTP {response.status_code}")
            try:
                print(response.json())
            except:
                pass
    except Exception as e:
        print(f"[Error] 無法連線至 Router: {e}")

def update_job(args):
    payload = {}
    if args.target: payload["target_agent"] = args.target
    if args.trigger: 
        payload["trigger"] = args.trigger
        valid, msg = validate_trigger_args(args)
        if not valid:
            print(f"[Error] {msg}")
            sys.exit(1)
            
    if args.prompt: payload["prompt"] = args.prompt
    if args.type: payload["type"] = args.type
    if args.hour is not None: payload["hour"] = args.hour
    if args.minute is not None: payload["minute"] = args.minute
    if args.second is not None: payload["second"] = args.second
    if args.day_of_week is not None: payload["day_of_week"] = args.day_of_week
    if args.day is not None: payload["day"] = args.day
    if args.hours is not None: payload["hours"] = args.hours
    if args.minutes is not None: payload["minutes"] = args.minutes
    if args.seconds is not None: payload["seconds"] = args.seconds
    if args.run_time: payload["run_time"] = args.run_time

    if not payload:
        print("[Error] 請提供至少一個要更新的參數")
        sys.exit(1)

    try:
        response = requests.put(f"{ROUTER_URL}/awake/jobs/{args.id}", json=payload, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success":
                print(f"[Success] 任務已更新: {args.id}")
            else:
                print(f"[Error] 更新失敗: {res_data.get('message', '未知錯誤')}")
        else:
            print(f"[Error] API 回應錯誤: HTTP {response.status_code}")
            try:
                print(response.json())
            except:
                pass
    except Exception as e:
        print(f"[Error] 無法連線至 Router: {e}")

def delete_job(args):
    try:
        response = requests.delete(f"{ROUTER_URL}/awake/jobs/{args.id}", timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success":
                print(f"[Success] 任務已刪除: {args.id}")
            else:
                print(f"[Error] 刪除失敗: {res_data.get('message', '未知錯誤')}")
        else:
            print(f"[Error] API 回應錯誤: HTTP {response.status_code}")
    except Exception as e:
        print(f"[Error] 無法連線至 Router: {e}")

def list_jobs(args):
    try:
        response = requests.get(f"{ROUTER_URL}/awake/jobs", timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            jobs = res_data.get("jobs", [])
            print(f"=== Awake 任務列表 (共 {len(jobs)} 筆) ===")
            for j in jobs:
                print(f"ID: {j.get('id')}")
                print(f"  目標: {j.get('target_agent')}")
                print(f"  排程: {j.get('trigger')}")
                print(f"  下次執行: {j.get('next_run_time')}")
                print(f"  指令: {j.get('prompt')}")
                print("-" * 30)
        else:
            print(f"[Error] API 回應錯誤: HTTP {response.status_code}")
    except Exception as e:
        print(f"[Error] 無法連線至 Router: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="OctoMatrix Awake 任務管理工具")
    subparsers = parser.add_subparsers(dest="command", help="子指令: register, update, delete, list")
    
    # 共用參數
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('--target', type=str, help='目標 Agent 名稱')
    parent_parser.add_argument('--trigger', type=str, help='排程類型 (cron, daily, weekly, monthly, interval, date)')
    parent_parser.add_argument('--prompt', type=str, help='執行指令內容')
    parent_parser.add_argument('--type', type=str, default='agent_command', help='任務類型 (預設: agent_command)')
    parent_parser.add_argument('--hour', type=int, help='小時')
    parent_parser.add_argument('--minute', type=int, help='分鐘')
    parent_parser.add_argument('--second', type=int, help='秒數')
    parent_parser.add_argument('--day_of_week', type=str, help='星期 (0-6 或 mon-sun)')
    parent_parser.add_argument('--day', type=int, help='日期')
    parent_parser.add_argument('--hours', type=int, help='間隔小時數')
    parent_parser.add_argument('--minutes', type=int, help='間隔分鐘數')
    parent_parser.add_argument('--seconds', type=int, help='間隔秒數')
    parent_parser.add_argument('--run_time', type=str, help='指定執行時間 (YYYY-MM-DD HH:MM:SS)')

    # Register
    parser_reg = subparsers.add_parser('register', parents=[parent_parser], help='註冊新任務')
    parser_reg.add_argument('--id', type=str, required=True, help='任務唯一 ID')
    
    # Update
    parser_upd = subparsers.add_parser('update', parents=[parent_parser], help='更新任務')
    parser_upd.add_argument('--id', type=str, required=True, help='任務唯一 ID')

    # Delete
    parser_del = subparsers.add_parser('delete', help='刪除任務')
    parser_del.add_argument('--id', type=str, required=True, help='任務唯一 ID')
    
    # List
    parser_list = subparsers.add_parser('list', help='列出所有任務')

    args = parser.parse_args()

    if args.command == 'register':
        if not args.target or not args.trigger or not args.prompt:
            print("[Error] register 指令必須提供 --target, --trigger 與 --prompt")
            sys.exit(1)
        register_job(args)
    elif args.command == 'update':
        update_job(args)
    elif args.command == 'delete':
        delete_job(args)
    elif args.command == 'list':
        list_jobs(args)
    else:
        parser.print_help()
