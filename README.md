# 自动化批量测试程序使用说明

## 功能概述

这个自动化测试程序用于批量测试LLM模型的性能，基于evalscope框架，支持多组参数组合测试，并将结果自动记录到CSV文件中。

## 文件说明

- `batch_test.py`: 主程序，执行自动化批量测试
- `test_config.yaml`: 配置文件，定义测试参数
- `read_config.py`: 配置文件读取工具

## 配置文件格式 (test_config.yaml)

```yaml
output_file: result.csv  # 输出CSV文件名

# 测试模式: all, prefill, decode
mode: all

# 模型配置
model_config:
  model: deepseek-v3
  url: http://10.119.194.202:8000/v1/chat/completions
  api: openai
  api_key: sk-1e1b3bec65824ecc818d1cb0ff30f3e1
  tokenizer_path: /workspace/models/DeepSeek-V3.1-Terminus

# 测试配置
eval_config:
  # benchmark参数（这三个参数需要对齐）
  number: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]  # 总请求数
  concurrency: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]  # 并发数
  rate: 2  # 请求速率（可以是单值或数组）
  
  # 输入输出参数（这三个参数需要对齐）
  input_tokens: 1024  # 输入长度
  output_tokens: 1024  # 输出长度
  prefix_length: 0  # 前缀长度
```

## 测试模式 (mode)

程序支持三种测试模式，用于记录不同的性能指标：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `all` | 记录所有指标（默认） | 完整性能分析 |
| `prefill` | 只记录预填充阶段相关指标 | 测试首token延迟和输入处理能力 |
| `decode` | 只记录解码阶段相关指标 | 测试生成速度和输出吞吐量 |

### 各模式输出字段

**all 模式**：
- input_tokens, prefix_length, output_tokens, rate, concurrency, number
- ttft, p90_ttft, tpot, p90_tpot, input_token_throughput, output_token_throughput

**prefill 模式**：
- input_tokens, output_tokens, concurrency, number, ttft, p90_ttft, input_token_throughput

**decode 模式**：
- input_tokens, prefix_length, output_tokens, tpot, p90_tpot, concurrency, number, output_token_throughput

## 参数对齐规则

### 第一组：number, concurrency, rate
- 这三个参数的数组长度需要对齐
- 如果某个参数是单值或长度为1的数组，会自动扩充到最大长度
- 如果数组长度不为1且不一致，程序会报错

### 第二组：input_tokens, output_tokens, prefix_length
- 这三个参数的数组长度需要对齐
- 同样支持自动扩充

### 测试组合
- 每组(input_tokens, output_tokens, prefix_length)对应完整的(number, concurrency, rate)测试
- 总测试数 = len(第一组) × len(第二组)

**示例**：
- input_tokens数组长度为3
- number数组长度为7
- 总共会执行 3 × 7 = 21 组测试

## CSV输出格式

输出的CSV文件根据 `mode` 设置包含不同的列。以下是 `all` 模式下的完整列说明：

| 列名 | 说明 | 来源 | all | prefill | decode |
|------|------|------|:---:|:-------:|:------:|
| input_tokens | 输入token数量 | 配置文件 | ✓ | ✓ | ✓ |
| prefix_length | 前缀长度 | 配置文件 | ✓ | | ✓ |
| output_tokens | 输出token数量 | 配置文件 | ✓ | ✓ | ✓ |
| rate | 请求速率 | 配置文件 | ✓ | | |
| concurrency | 并发数 | 配置文件 | ✓ | ✓ | ✓ |
| number | 总请求数 | 配置文件 | ✓ | ✓ | ✓ |
| ttft | 平均首token时间(秒) | Average time to first token | ✓ | ✓ | |
| p90_ttft | 90分位首token时间(秒) | Percentiles TTFT 90% | ✓ | ✓ | |
| tpot | 平均每token时间(秒) | Average time per output token | ✓ | | ✓ |
| p90_tpot | 90分位每token时间(秒) | Percentiles TPOT 90% | ✓ | | ✓ |
| input_token_throughput | 输入token吞吐量(tok/s) | Total - Output throughput | ✓ | ✓ | |
| output_token_throughput | 输出token吞吐量(tok/s) | Output token throughput | ✓ | | ✓ |

## 使用方法

1. 确保已安装依赖：
```bash
pip install evalscope pyyaml
```

2. 编辑配置文件 `test_config.yaml`，设置：
   - 测试模式 (`mode`: all/prefill/decode)
   - 模型访问参数
   - 测试参数组合
   - 输出文件名

3. 运行测试程序：
```bash
python auto_test.py
```

或者指定配置文件：
```python
from auto_test import run_auto_test
run_auto_test("test_config.yaml")
```

## 输出示例

程序运行时会显示进度：

```
总共需要运行 21 组测试

[1/21] 运行测试:
  input_tokens=1024, output_tokens=1024, prefix_length=0
  number=1, concurrency=1, rate=2
  ✓ 测试完成，结果已写入 result.csv
    TTFT: 0.4146s, TPOT: 0.0206s, Output throughput: 35.07 tok/s

[2/21] 运行测试:
  ...
```

## 注意事项

1. **文件追加**：如果输出文件已存在，新的测试结果会追加到文件末尾
2. **错误处理**：某个测试失败不会中断整个流程，会继续执行下一个测试
3. **数组对齐**：请确保参数数组长度符合对齐规则，否则程序会报错
4. **测试时间**：大量测试组合可能需要较长时间，请耐心等待
5. **自动清理**：每次测试完成后会自动删除evalscope生成的`outputs`文件夹，保持目录整洁

## 配置示例

### 示例1：单组参数测试
```yaml
eval_config:
  number: 100
  concurrency: 10
  rate: 5
  input_tokens: 1024
  output_tokens: 1024
  prefix_length: 0
```
总测试数：1 × 1 = 1

### 示例2：多并发测试
```yaml
eval_config:
  number: [10, 50, 100]
  concurrency: [1, 5, 10]
  rate: 10
  input_tokens: 1024
  output_tokens: 1024
  prefix_length: 0
```
总测试数：3 × 1 = 3

### 示例3：多输入输出长度测试
```yaml
eval_config:
  number: 100
  concurrency: 10
  rate: 5
  input_tokens: [512, 1024, 2048]
  output_tokens: [256, 512, 1024]
  prefix_length: [0, 0, 0]
```
总测试数：1 × 3 = 3

### 示例4：完整组合测试
```yaml
eval_config:
  number: [10, 50, 100]
  concurrency: [1, 5, 10]
  rate: 10
  input_tokens: [512, 1024]
  output_tokens: [256, 512]
  prefix_length: 0
```
总测试数：3 × 2 = 6

### 示例5：Prefill模式测试（测试首token延迟）
```yaml
mode: prefill

eval_config:
  number: [1000, 2000]
  concurrency: [1000, 2000]
  rate: 50
  input_tokens: [1024, 2048, 4096]
  output_tokens: 1  # prefill模式下output_tokens通常设为1
  prefix_length: 0
```
输出字段：input_tokens, output_tokens, concurrency, number, ttft, p90_ttft, input_token_throughput

### 示例6：Decode模式测试（测试生成速度）
```yaml
mode: decode

eval_config:
  number: 100
  concurrency: [8, 16, 32]
  rate: -1
  input_tokens: 1024
  output_tokens: [512, 1024, 2048]
  prefix_length: 0
```
输出字段：input_tokens, prefix_length, output_tokens, tpot, p90_tpot, concurrency, number, output_token_throughput

