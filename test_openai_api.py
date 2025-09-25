#!/usr/bin/env python3
"""
OpenAI API Key Validation Script

This script validates the OpenAI API key format and tests the API connection.
"""

import os
import sys
import requests
from typing import Optional


def validate_api_key_format(api_key: str) -> bool:
    """
    Validate OpenAI API key format.
    
    Args:
        api_key: The API key to validate
        
    Returns:
        bool: True if format is valid, False otherwise
    """
    # Check if API key starts with correct prefix
    if not api_key.startswith('sk-proj-'):
        print("❌ APIキーの形式が正しくありません")
        print("OpenAI APIキーは 'sk-proj-' で始まる必要があります")
        return False
    
    # Check minimum length
    if len(api_key) < 50:
        print("❌ APIキーの長さが正しくありません")
        print("OpenAI APIキーは約51文字である必要があります")
        return False
    
    print("✅ APIキーの形式が正しく設定されています")
    return True


def test_openai_api(api_key: str) -> bool:
    """
    Test OpenAI API connection.
    
    Args:
        api_key: The API key to test
        
    Returns:
        bool: True if API call succeeds, False otherwise
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": "Hello, this is a test message."}
            ],
            "max_tokens": 10
        }
        
        print("🔄 OpenAI APIをテスト中...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ OpenAI API接続テストが成功しました")
            return True
        else:
            print(f"❌ OpenAI API接続テストが失敗しました: {response.status_code}")
            print(f"エラー詳細: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ネットワークエラーが発生しました: {e}")
        return False
    except Exception as e:
        print(f"❌ 予期しないエラーが発生しました: {e}")
        return False


def main() -> bool:
    """
    Main function to validate and test OpenAI API key.
    
    Returns:
        bool: True if all tests pass, False otherwise
    """
    print("🔍 OpenAI API Key Validation Script")
    print("=" * 50)
    
    # Get API key from environment variable
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY環境変数が設定されていません")
        print("以下のコマンドで設定してください:")
        print("export OPENAI_API_KEY='sk-proj-your-api-key-here'")
        return False
    
    # Validate API key format
    if not validate_api_key_format(api_key):
        return False
    
    # Test API connection
    if not test_openai_api(api_key):
        return False
    
    print("\n🎉 すべてのテストが成功しました！")
    print("OpenAI APIキーが正常に設定され、動作しています。")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)