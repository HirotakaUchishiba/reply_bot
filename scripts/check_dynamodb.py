#!/usr/bin/env python3
"""
DynamoDBテーブルの内容を確認するスクリプト
"""

import boto3
import json
import os
from typing import Dict, Any, List
from datetime import datetime


def get_dynamodb_client():
    """DynamoDBクライアントを取得"""
    region = os.getenv('AWS_REGION', 'ap-northeast-1')
    return boto3.client('dynamodb', region_name=region)


def list_tables(client) -> List[str]:
    """テーブル一覧を取得"""
    response = client.list_tables()
    return response.get('TableNames', [])


def describe_table(client, table_name: str) -> Dict[str, Any]:
    """テーブルの詳細情報を取得"""
    return client.describe_table(TableName=table_name)


def scan_table(client, table_name: str, limit: int = 10) -> Dict[str, Any]:
    """テーブル内のアイテムをスキャン"""
    return client.scan(
        TableName=table_name,
        Limit=limit
    )


def get_item(client, table_name: str, context_id: str) -> Dict[str, Any]:
    """特定のアイテムを取得"""
    return client.get_item(
        TableName=table_name,
        Key={'context_id': {'S': context_id}}
    )


def format_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """DynamoDBアイテムを読みやすい形式に変換"""
    formatted = {}
    for key, value in item.items():
        if 'S' in value:
            formatted[key] = value['S']
        elif 'N' in value:
            formatted[key] = int(value['N'])
        elif 'BOOL' in value:
            formatted[key] = value['BOOL']
        elif 'M' in value:
            formatted[key] = format_item(value['M'])
        else:
            formatted[key] = value
    return formatted


def main():
    """メイン処理"""
    client = get_dynamodb_client()
    
    # テーブル一覧を表示
    print("=== DynamoDBテーブル一覧 ===")
    tables = list_tables(client)
    for table in tables:
        print(f"- {table}")
    
    # reply-bot関連のテーブルを探す
    reply_bot_tables = [t for t in tables if 'reply-bot' in t]
    
    if not reply_bot_tables:
        print("\nreply-bot関連のテーブルが見つかりません。")
        return
    
    table_name = reply_bot_tables[0]
    print(f"\n=== テーブル詳細: {table_name} ===")
    
    # テーブル詳細を表示
    table_info = describe_table(client, table_name)
    print(f"テーブル名: {table_info['Table']['TableName']}")
    print(f"アイテム数: {table_info['Table']['ItemCount']}")
    print(f"テーブルサイズ: {table_info['Table']['TableSizeBytes']} bytes")
    print(f"作成日時: {table_info['Table']['CreationDateTime']}")
    
    # テーブル内のアイテムをスキャン
    print(f"\n=== テーブル内のアイテム (最大10件) ===")
    scan_result = scan_table(client, table_name)
    
    if scan_result.get('Items'):
        for i, item in enumerate(scan_result['Items'], 1):
            formatted_item = format_item(item)
            print(f"\n--- アイテム {i} ---")
            print(json.dumps(formatted_item, indent=2, ensure_ascii=False))
    else:
        print("テーブル内にアイテムがありません。")
    
    # 特定のcontext_idでアイテムを取得する例
    if scan_result.get('Items'):
        first_item = scan_result['Items'][0]
        context_id = first_item.get('context_id', {}).get('S')
        if context_id:
            print(f"\n=== 特定アイテムの取得例 (context_id: {context_id}) ===")
            item_result = get_item(client, table_name, context_id)
            if 'Item' in item_result:
                formatted_item = format_item(item_result['Item'])
                print(json.dumps(formatted_item, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

