#!/usr/bin/env python3
"""测试 MiniMax Coding Plan API"""

import anthropic

# 配置
API_KEY = "sk-cp-1WyWKf2nLFunO_xvp91HV8jftFcBT2CdA-z5zGAuRUvjS57Ffcp8Ty1bmi5MWcXTeH66L5aFkGyFat0sWimXeGEzuLKJ5l_Eu12DC91i3HXfMBWHVe1kMLk"
BASE_URL = "https://api.minimaxi.com/anthropic"  # 国内地址

print(f"测试 MiniMax Coding Plan API")
print(f"Base URL: {BASE_URL}")
print(f"API Key: {API_KEY[:20]}...")
print("-" * 60)

try:
    # 创建客户端
    client = anthropic.Anthropic(
        api_key=API_KEY,
        base_url=BASE_URL
    )
    
    # 发送测试请求
    print("发送测试请求...")
    message = client.messages.create(
        model="MiniMax-M2.5",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": "你好，请用一句话介绍你自己。"
        }]
    )
    
    # 输出结果
    print("\n✅ API 调用成功！")
    print(f"模型: {message.model}")
    print(f"使用 tokens: input={message.usage.input_tokens}, output={message.usage.output_tokens}")
    print(f"\n回复内容:")
    for block in message.content:
        if block.type == "text":
            print(block.text)
    
except Exception as e:
    print(f"\n❌ API 调用失败: {e}")
    import traceback
    traceback.print_exc()
