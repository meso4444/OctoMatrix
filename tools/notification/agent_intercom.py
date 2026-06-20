#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
內部橫向通訊封裝 (agent_intercom.py)
"""
import os
import sys
import argparse
import requests

def get_router_url() -> str:
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        port_file = os.path.join(curr, '.router_port')
        if os.path.exists(port_file):
            try:
                with open(port_file, 'r') as f:
                    p = f.read().strip()
                    if p: return f"http://localhost:{p}"
            except: pass
        curr = os.path.dirname(curr)
    return f"http://localhost:{os.getenv('ROUTER_PORT', 12210)}"

def get_source_agent() -> str:
    # 嘗試從環境變數或專案狀態中取得
    agent_name = os.getenv("AGENT_NAME")
    if agent_name: return agent_name
    
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        env_file = os.path.join(curr, 'octo_cyberbrain', '.cyberbrain_env')
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith("AGENT_NAME="):
                            return line.strip().split('=', 1)[1]
            except: pass
        curr = os.path.dirname(curr)
    return "UnknownAgent"

def main():
    parser = argparse.ArgumentParser(description="Agent-to-Agent 通訊發送器")
    parser.add_argument("--target", required=True, help="目標 Agent 的名字")
    parser.add_argument("--message", required=True, help="要傳遞的訊息或指令")
    args = parser.parse_args()

    router_url = f"{get_router_url()}/inter-agent/message"
    source_agent = get_source_agent()

    SYS_PREFIX = "【系統提示】"
    sop_template = f"""{SYS_PREFIX}
執行以下 [SOP]:
[Step 0 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖。
[Step 1 - 辨識]：辨識 Source Agent 的訊息是否為未完成協作任務，若為未完成協作任務則進入Step2; 若非則執行 python3 toolbox/matrix_notifier.py '{{向{{MATRIX_USERNAME}}報告協作任務的完成狀態}}'，並且不執行後續Step。
[Step 2 - 梳理]：若協作任務明確則執行 python3 toolbox/matrix_notifier.py '{{向{{MATRIX_USERNAME}}問候，並自主思考合適的初步預告}}' 預告協作進行的初步方向，並且進入Step3; 若不明確，則先中止任務並執行 python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{你的訊息...}}" 向 Source Agent 詢問具體方向，不執行後續Step。
[Step 3 - 執行]：正式開始執行協作任務並撰寫md。若協作任務仍需要與 Source Agent 進行階段性交接或者完工驗證，則執行 python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{你的訊息...}}" 進行 Agent 間通訊交接，且不執行後續Step; 若協作任務已確認完工或失敗則進入Step4。
[Step 4 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖。
[Step 5 - 回報User]：執行 python3 toolbox/matrix_notifier.py '{{向{{MATRIX_USERNAME}}回報傳遞成功通知或失敗異常}}'。
[Step 6 - 回報Agent]：執行 python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{說明完工或失敗狀態，並且註明此訊息不需再進行Agent通訊回覆避免進入無限迴圈，若有疑義則詢問{{MATRIX_USERNAME}}}}"
[Step 7 - 收攝]：執行 python3 octo_cyberbrain/octo_ghost_reader.py --level current 收攝你的 GHOST 與記憶。
[Step 8 - 刻印]：執行 python3 octo_cyberbrain/octo_ghost_updater.py --outline "語義大綱" --keywords "關鍵字1,關鍵字2" --paths "/檔案路徑1,/檔案路徑2" 將本次任務狀態刻印到GHOST。

來自 {source_agent} 的訊息:
{args.message}

{SYS_PREFIX}請務必嚴格遵守上述 [SOP] 進行回覆。"""

    payload = {
        "source": source_agent,
        "target_agent": args.target,
        "message": sop_template
    }

    try:
        response = requests.post(router_url, json=payload, timeout=5)
        response.raise_for_status()
        result = response.json()
        if result.get("status") == "success":
            print(f"✅ 成功發送訊息至 {args.target}")
            sys.exit(0)
        else:
            print(f"❌ 傳送失敗: {result.get('error', 'Unknown Error')}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ API 請求異常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
