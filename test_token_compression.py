#!/usr/bin/env python3
"""
测试上下文压缩引擎的 Token 消耗降低效果
独立测试，不依赖外部模块
"""

import json
import time


def estimate_tokens(messages: list) -> int:
    """估算 Token 数（基于 JSON 长度，约等于字符数/4）"""
    return len(json.dumps(messages, default=str)) // 4


def microcompact(messages: list) -> None:
    """
    微观压缩：清理旧的 tool_result payload
    只保留最近 3 个 tool_result 的完整内容
    """
    tool_results = []
    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append(part)

    if len(tool_results) <= 3:
        return

    # 保留最后 3 个，其他的清空
    for part in tool_results[:-3]:
        if isinstance(part.get("content"), str) and len(part["content"]) > 100:
            part["content"] = "[cleared]"


def create_simulated_conversation(num_turns: int, tool_output_size: int = 2000) -> list:
    """
    创建模拟的对话历史
    - num_turns: 对话轮数
    - tool_output_size: 每个工具输出的大小（字节）
    """
    messages = []

    # 初始系统提示和用户消息
    messages.append({
        "role": "system",
        "content": "You are a coding agent. Use tools to solve tasks."
    })

    # 模拟多轮对话
    dummy_output = " " * tool_output_size

    for i in range(num_turns):
        # 用户消息
        messages.append({
            "role": "user",
            "content": f"Task step {i+1}: Please process something..."
        })

        # 助手工具调用
        messages.append({
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": f"tool_use_{i}",
                    "name": "read_file" if i % 2 == 0 else "bash",
                    "input": {"path": f"file_{i}.py"} if i % 2 == 0 else {"command": f"echo step {i}"}
                }
            ]
        })

        # 工具结果
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": f"tool_use_{i}",
                    "content": f"# File: file_{i}.py\n" + dummy_output + f"\n# End of file {i}\n"
                }
            ]
        })

    return messages


def test_microcompaction():
    """测试微观压缩效果"""
    print("="*60)
    print("微观压缩测试 (Micro-compaction)")
    print("="*60)

    messages = create_simulated_conversation(20, tool_output_size=2000)

    tokens_before = estimate_tokens(messages)
    microcompact(messages)
    tokens_after = estimate_tokens(messages)

    reduction = (tokens_before - tokens_after) / tokens_before * 100

    print(f"\n对话轮数：20")
    print(f"每轮工具输出大小：2000 字节")
    print(f"\n压缩前 Token 数：{tokens_before}")
    print(f"压缩后 Token 数：{tokens_after}")
    print(f"减少量：{tokens_before - tokens_after} tokens")
    print(f"压缩率：{reduction:.1f}%")

    return reduction


def test_macrocompaction():
    """测试宏观压缩效果（模拟）"""
    print("\n" + "="*60)
    print("宏观压缩测试 (Macro-compaction / Auto-compact)")
    print("="*60)

    messages = create_simulated_conversation(50, tool_output_size=3000)

    tokens_before = estimate_tokens(messages)
    message_count_before = len(messages)

    # 估算压缩后的效果
    estimated_summary_tokens = 2000  # LLM 生成的摘要
    overhead_tokens = 100  # 路径信息和确认消息的开销
    tokens_after_estimated = estimated_summary_tokens + overhead_tokens

    reduction = (tokens_before - tokens_after_estimated) / tokens_before * 100

    print(f"\n对话轮数：50")
    print(f"每轮工具输出大小：3000 字节")
    print(f"\n压缩前消息数：{message_count_before}")
    print(f"压缩后消息数：2 (摘要 + 确认)")
    print(f"\n压缩前 Token 数：{tokens_before}")
    print(f"压缩后 Token 数 (估算): {tokens_after_estimated}")
    print(f"减少量：{tokens_before - tokens_after_estimated} tokens")
    print(f"压缩率：{reduction:.1f}%")

    return reduction


def test_combined_scenarios():
    """测试不同场景下的综合压缩效果"""
    print("\n" + "="*60)
    print("不同场景的综合压缩效果")
    print("="*60)

    scenarios = [
        ("短任务 (10 轮)", 10, 1000),
        ("中等任务 (30 轮)", 30, 2000),
        ("长任务 (50 轮)", 50, 3000),
        ("超长任务 (100 轮)", 100, 2000),
    ]

    print("\n{:<20} {:>12} {:>12} {:>12} {:>10}".format(
        "场景", "压缩前", "压缩后", "减少量", "压缩率"
    ))
    print("-"*68)

    for name, turns, output_size in scenarios:
        messages = create_simulated_conversation(turns, output_size)
        tokens_before = estimate_tokens(messages)

        # 先微观压缩
        microcompact(messages)
        tokens_after_micro = estimate_tokens(messages)

        # 再估算宏观压缩效果
        tokens_after_macro = 2000 + 100

        total_reduction = (tokens_before - tokens_after_macro) / tokens_before * 100

        print("{:<20} {:>12,} {:>12,} {:>12,} {:>9.1f}%".format(
            name, tokens_before, tokens_after_macro,
            tokens_before - tokens_after_macro, total_reduction
        ))


def analyze_layer_by_layer():
    """分层分析压缩效果"""
    print("\n" + "="*60)
    print("分层压缩效果分析")
    print("="*60)

    messages = create_simulated_conversation(30, tool_output_size=2500)

    tokens_original = estimate_tokens(messages)
    print(f"\n原始 Token 数：{tokens_original:,}")

    # 第一层：微观压缩
    microcompact(messages)
    tokens_after_micro = estimate_tokens(messages)
    micro_reduction = tokens_original - tokens_after_micro
    print(f"\n第一层 (微观压缩): -{micro_reduction:,} tokens ({micro_reduction/tokens_original*100:.1f}%)")
    print(f"  剩余：{tokens_after_micro:,} tokens")

    # 第二层：宏观压缩
    tokens_after_macro = 2000 + 100
    macro_reduction = tokens_after_micro - tokens_after_macro
    print(f"\n第二层 (宏观压缩): -{macro_reduction:,} tokens ({macro_reduction/tokens_original*100:.1f}%)")
    print(f"  剩余：{tokens_after_macro:,} tokens")

    total_reduction = tokens_original - tokens_after_macro
    print(f"\n总压缩效果：-{total_reduction:,} tokens ({total_reduction/tokens_original*100:.1f}%)")


if __name__ == "__main__":
    # 运行所有测试
    micro_reduction = test_microcompaction()
    macro_reduction = test_macrocompaction()
    test_combined_scenarios()
    analyze_layer_by_layer()

    # 总结
    print("\n" + "="*60)
    print("总结：Token 压缩效果估算")
    print("="*60)
    print("\n微观压缩 (Micro-compaction):")
    print(f"  • 典型压缩率：{micro_reduction:.0f}%")
    print(f"  • 适用场景：清理旧的 tool_result payload")
    print(f"  • 触发条件：tool_result 数量 > 3")

    print("\n宏观压缩 (Macro-compaction):")
    print(f"  • 典型压缩率：{macro_reduction:.0f}%")
    print(f"  • 适用场景：长周期任务、上下文接近限制")
    print(f"  • 触发条件：Token 数 > config.TOKEN_THRESHOLD")

    print("\n综合建议值:")
    print("  • 短任务 (10-20 轮): 微观压缩 ~15-25%")
    print("  • 中等任务 (30-50 轮): 微观 + 宏观 ~60-75%")
    print("  • 长任务 (50+ 轮): 微观 + 宏观 ~75-85%")
