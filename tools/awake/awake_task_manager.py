#!/usr/bin/env python3
import os
import sys
import argparse
import requests
import json

# Upward search to find the nearest .router_port or .cyberbrain_env
def get_router_url():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try finding .router_port
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
        
    # Try finding .cyberbrain_env
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
    """Front-end parameter validation to ensure corresponding scheduling parameters are provided"""
    if args.trigger == 'daily' or args.trigger == 'cron':
        if args.hour is None or args.minute is None:
            return False, "When trigger is 'daily' or 'cron', --hour and --minute must be specified"
    elif args.trigger == 'weekly':
        if args.day_of_week is None or args.hour is None or args.minute is None:
            return False, "When trigger is 'weekly', --day_of_week, --hour, and --minute must be specified"
    elif args.trigger == 'monthly':
        if args.day is None or args.hour is None or args.minute is None:
            return False, "When trigger is 'monthly', --day, --hour, and --minute must be specified"
    elif args.trigger == 'date':
        if not args.run_time:
            return False, "When trigger is 'date', --run_time must be specified"
    elif args.trigger == 'interval':
        if args.hours is None and args.minutes is None and args.seconds is None:
            return False, "When trigger is 'interval', at least one of --hours, --minutes, or --seconds must be specified"
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
                print(f"[Success] Task registered: {args.id}")
            else:
                print(f"[Error] Registration failed: {res_data.get('message', 'Unknown error')}")
        else:
            print(f"[Error] API response error: HTTP {response.status_code}")
            try:
                print(response.json())
            except:
                pass
    except Exception as e:
        print(f"[Error] Cannot connect to Router: {e}")

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
        print("[Error] Please provide at least one parameter to update")
        sys.exit(1)

    try:
        response = requests.put(f"{ROUTER_URL}/awake/jobs/{args.id}", json=payload, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success":
                print(f"[Success] Task updated: {args.id}")
            else:
                print(f"[Error] Update failed: {res_data.get('message', 'Unknown error')}")
        else:
            print(f"[Error] API response error: HTTP {response.status_code}")
            try:
                print(response.json())
            except:
                pass
    except Exception as e:
        print(f"[Error] Cannot connect to Router: {e}")

def delete_job(args):
    try:
        response = requests.delete(f"{ROUTER_URL}/awake/jobs/{args.id}", timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success":
                print(f"[Success] Task deleted: {args.id}")
            else:
                print(f"[Error] Deletion failed: {res_data.get('message', 'Unknown error')}")
        else:
            print(f"[Error] API response error: HTTP {response.status_code}")
    except Exception as e:
        print(f"[Error] Cannot connect to Router: {e}")

def list_jobs(args):
    try:
        response = requests.get(f"{ROUTER_URL}/awake/jobs", timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            jobs = res_data.get("jobs", [])
            print(f"=== Awake Task List (Total: {len(jobs)}) ===")
            for j in jobs:
                print(f"ID: {j.get('id')}")
                print(f"  Target: {j.get('target_agent')}")
                print(f"  Trigger: {j.get('trigger')}")
                print(f"  Next Run: {j.get('next_run_time')}")
                print(f"  Command: {j.get('prompt')}")
                print("-" * 30)
        else:
            print(f"[Error] API response error: HTTP {response.status_code}")
    except Exception as e:
        print(f"[Error] Cannot connect to Router: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="OctoMatrix Awake Task Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands: register, update, delete, list")
    
    # Common parameters
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('--target', type=str, help='Target Agent Name')
    parent_parser.add_argument('--trigger', type=str, help='Trigger type (cron, daily, weekly, monthly, interval, date)')
    parent_parser.add_argument('--prompt', type=str, help='Command content')
    parent_parser.add_argument('--type', type=str, default='agent_command', help='Task type (default: agent_command)')
    parent_parser.add_argument('--hour', type=int, help='Hour')
    parent_parser.add_argument('--minute', type=int, help='Minute')
    parent_parser.add_argument('--second', type=int, help='Second')
    parent_parser.add_argument('--day_of_week', type=str, help='Day of week (0-6 or mon-sun)')
    parent_parser.add_argument('--day', type=int, help='Day of month')
    parent_parser.add_argument('--hours', type=int, help='Interval hours')
    parent_parser.add_argument('--minutes', type=int, help='Interval minutes')
    parent_parser.add_argument('--seconds', type=int, help='Interval seconds')
    parent_parser.add_argument('--run_time', type=str, help='Specific run time (YYYY-MM-DD HH:MM:SS)')

    # Register
    parser_reg = subparsers.add_parser('register', parents=[parent_parser], help='Register a new task')
    parser_reg.add_argument('--id', type=str, required=True, help='Unique task ID')
    
    # Update
    parser_upd = subparsers.add_parser('update', parents=[parent_parser], help='Update a task')
    parser_upd.add_argument('--id', type=str, required=True, help='Unique task ID')

    # Delete
    parser_del = subparsers.add_parser('delete', help='Delete a task')
    parser_del.add_argument('--id', type=str, required=True, help='Unique task ID')
    
    # List
    parser_list = subparsers.add_parser('list', help='List all tasks')

    args = parser.parse_args()

    if args.command == 'register':
        if not args.target or not args.trigger or not args.prompt:
            print("[Error] register command must provide --target, --trigger, and --prompt")
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